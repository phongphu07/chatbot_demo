import json
import logging
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import numpy as np
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from pgvector.psycopg2 import register_vector
from app.config import settings
from app.cache import rag_cache

logger = logging.getLogger(__name__)

class VectorStore:
    """
    High-Performance Vector Store với ThreadedConnectionPool và HNSW Index trên PostgreSQL pgvector.
    Hỗ trợ xử lý đồng thời hàng nghìn kết nối với độ trễ thấp (< 5ms).
    """
    def __init__(self):
        self.is_postgres_connected = False
        self._pool: Optional[ThreadedConnectionPool] = None
        self._memory_chunks: List[Dict[str, Any]] = []
        self._init_database()

    def _init_database(self):
        """Khởi tạo Connection Pool và schema PostgreSQL + pgvector"""
        try:
            # 1. Khởi tạo ThreadedConnectionPool cho đa luồng chịu tải cao
            self._pool = ThreadedConnectionPool(
                minconn=2,
                maxconn=30,
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                dbname=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                connect_timeout=3
            )
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Kích hoạt extension pgvector
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    register_vector(conn)
                    
                    # Tạo bảng document_chunks
                    dim = settings.embedding_dim
                    cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id BIGSERIAL PRIMARY KEY,
                        doc_name VARCHAR(255) NOT NULL,
                        chunk_index INT NOT NULL,
                        content TEXT NOT NULL,
                        contextual_content TEXT,
                        metadata JSONB,
                        embedding VECTOR({dim}),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    """)

                    # Tạo HNSW index cho cosine similarity
                    cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_doc_chunks_hnsw 
                    ON document_chunks USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64);
                    """)
                    conn.commit()

            self.is_postgres_connected = True
            logger.info("Ket noi thanh cong toi PostgreSQL voi ThreadedConnectionPool va HNSW index!")
        except Exception as e:
            self.is_postgres_connected = False
            self._pool = None
            logger.warning(f"Chua the ket noi PostgreSQL ({e}). Dang su dung In-Memory Vector Store du phong.")

    @contextmanager
    def get_connection(self):
        """Borrow một connection từ pool và trả lại tự động khi xong (Thread-safe)"""
        if not self._pool:
            raise RuntimeError("PostgreSQL Connection Pool chua khoi tao")
        conn = self._pool.getconn()
        try:
            register_vector(conn)
            yield conn
        finally:
            self._pool.putconn(conn)

    def save_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> int:
        """Lưu danh sách chunk và vector tương ứng vào Database"""
        if not chunks or not embeddings:
            return 0

        # Xóa cache cũ khi có dữ liệu mới
        rag_cache.clear()

        if self.is_postgres_connected and self._pool:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        for chunk, emb in zip(chunks, embeddings):
                            cur.execute(
                                """
                                INSERT INTO document_chunks 
                                (doc_name, chunk_index, content, contextual_content, metadata, embedding)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                """,
                                (
                                    chunk["doc_name"],
                                    chunk["chunk_index"],
                                    chunk["content"],
                                    chunk.get("contextual_content", chunk["content"]),
                                    json.dumps(chunk.get("metadata", {})),
                                    np.array(emb, dtype=np.float32)
                                )
                            )
                        conn.commit()
                return len(chunks)
            except Exception as e:
                logger.error(f"Lỗi khi lưu vào PostgreSQL: {e}. Lưu vào Memory fallback.")

        # Fallback vào Memory Store
        for chunk, emb in zip(chunks, embeddings):
            self._memory_chunks.append({
                "id": len(self._memory_chunks) + 1,
                "doc_name": chunk["doc_name"],
                "chunk_index": chunk["chunk_index"],
                "content": chunk["content"],
                "contextual_content": chunk.get("contextual_content", chunk["content"]),
                "metadata": chunk.get("metadata", {}),
                "embedding": np.array(emb, dtype=np.float32)
            })
        return len(chunks)

    def search_similar_chunks(
        self,
        query_vector: List[float],
        top_k: int = 3,
        min_similarity: float = 0.35
    ) -> List[Dict[str, Any]]:
        """Tìm kiếm các chunk có độ tương đồng cosine cao nhất với query_vector (Dùng Connection Pool)"""
        if not query_vector:
            return []

        # 1. Truy vấn từ PostgreSQL + pgvector
        if self.is_postgres_connected and self._pool:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        query_vec_np = np.array(query_vector, dtype=np.float32)
                        cur.execute(
                            """
                            SELECT id, doc_name, chunk_index, content, metadata,
                                   (1 - (embedding <=> %s)) AS similarity
                            FROM document_chunks
                            ORDER BY embedding <=> %s
                            LIMIT %s;
                            """,
                            (query_vec_np, query_vec_np, top_k)
                        )
                        rows = cur.fetchall()
                        results = []
                        for row in rows:
                            sim = float(row[5])
                            if sim >= min_similarity:
                                results.append({
                                    "id": row[0],
                                    "doc_name": row[1],
                                    "chunk_index": row[2],
                                    "content": row[3],
                                    "metadata": row[4],
                                    "similarity": round(sim, 4)
                                })
                        return results
            except Exception as e:
                logger.error(f"Lỗi tìm kiếm trên Postgres: {e}")

        # 2. Truy vấn từ In-Memory Store nếu Postgres không có sẵn
        if not self._memory_chunks:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        scored = []
        for item in self._memory_chunks:
            c_vec = item["embedding"]
            c_norm = np.linalg.norm(c_vec)
            if c_norm == 0:
                continue
            cos_sim = float(np.dot(q_vec, c_vec) / (q_norm * c_norm))
            if cos_sim >= min_similarity:
                scored.append((cos_sim, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for sim, item in scored[:top_k]:
            results.append({
                "id": item["id"],
                "doc_name": item["doc_name"],
                "chunk_index": item["chunk_index"],
                "content": item["content"],
                "metadata": item["metadata"],
                "similarity": round(sim, 4)
            })
        return results

    def list_documents(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các tài liệu đã được index và số lượng chunk"""
        if self.is_postgres_connected and self._pool:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                        SELECT doc_name, COUNT(*) as chunk_count, MAX(created_at) as created_at
                        FROM document_chunks
                        GROUP BY doc_name
                        ORDER BY created_at DESC;
                        """)
                        rows = cur.fetchall()
                        return [
                            {"doc_name": r[0], "chunk_count": r[1], "created_at": str(r[2])}
                            for r in rows
                        ]
            except Exception as e:
                logger.error(f"Lỗi list_documents trên Postgres: {e}")

        # Memory summary
        summary = {}
        for item in self._memory_chunks:
            doc = item["doc_name"]
            summary[doc] = summary.get(doc, 0) + 1
        return [{"doc_name": k, "chunk_count": v, "created_at": "Hiện tại"} for k, v in summary.items()]

    def delete_document(self, doc_name: str) -> int:
        """Xóa tài liệu và toàn bộ chunk của nó"""
        rag_cache.clear()
        if self.is_postgres_connected and self._pool:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM document_chunks WHERE doc_name = %s;", (doc_name,))
                        deleted = cur.rowcount
                        conn.commit()
                        return deleted
            except Exception as e:
                logger.error(f"Lỗi delete_document trên Postgres: {e}")

        before_count = len(self._memory_chunks)
        self._memory_chunks = [c for c in self._memory_chunks if c["doc_name"] != doc_name]
        return before_count - len(self._memory_chunks)

    def get_status(self) -> Dict[str, Any]:
        """Kiểm tra trạng thái kết nối và số lượng chunks hiện có"""
        if not self.is_postgres_connected:
            self._init_database()

        if self.is_postgres_connected and self._pool:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) FROM document_chunks;")
                        total = cur.fetchone()[0]
                        return {
                            "mode": "PostgreSQL + pgvector (Connection Pool Active)",
                            "connected": True,
                            "pool_size": 30,
                            "total_chunks": total
                        }
            except Exception:
                self.is_postgres_connected = False

        return {
            "mode": "In-Memory Vector Store",
            "connected": False,
            "total_chunks": len(self._memory_chunks)
        }

vector_store = VectorStore()
