from typing import List
from app.config import settings

class EmbeddingService:
    def __init__(self):
        self._local_model = None

    @property
    def provider(self) -> str:
        return settings.EMBEDDING_PROVIDER

    def get_dimension(self) -> int:
        return settings.embedding_dim

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # 1. Google Gemini Embeddings
        if self.provider == "gemini":
            if not settings.GEMINI_API_KEY:
                raise ValueError("Chưa thiết lập GEMINI_API_KEY trong file .env!")
            from google import genai
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            
            # Sử dụng model gemini-embedding-001 (chuẩn hỗ trợ bởi Google GenAI SDK v1beta)
            # với output_dimensionality = settings.embedding_dim (768)
            try:
                response = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=texts,
                    config={"output_dimensionality": settings.embedding_dim}
                )
            except Exception:
                # Fallback thử lại text-embedding-004 nếu có
                response = client.models.embed_content(
                    model="text-embedding-004",
                    contents=texts
                )
            # Response chứa danh sách embedding
            if hasattr(response, "embeddings") and response.embeddings:
                return [list(emb.values) for emb in response.embeddings]
            elif hasattr(response, "embedding") and response.embedding:
                return [list(response.embedding.values)]
            else:
                raise RuntimeError("Định dạng phản hồi embedding không xác định từ Gemini.")

        # 2. OpenAI Embeddings
        elif self.provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("Chưa thiết lập OPENAI_API_KEY trong file .env!")
            import openai
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            res = client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            return [data.embedding for data in res.data]

        # 3. Local Sentence Transformers (Miễn phí, Offline)
        elif self.provider == "local":
            if self._local_model is None:
                from sentence_transformers import SentenceTransformer
                self._local_model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = self._local_model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()

        else:
            raise ValueError(f"Embedding provider không hợp lệ: {self.provider}")

    def embed_query(self, text: str) -> List[float]:
        from app.cache import rag_cache
        cache_key = f"emb:{text.strip().lower()}"
        cached = rag_cache.get(cache_key)
        if cached is not None:
            return cached

        results = self.embed_texts([text])
        if results:
            rag_cache.set(cache_key, results[0], ttl=3600) # Cache 1 giờ cho embedding câu hỏi
            return results[0]
        return []

embedding_service = EmbeddingService()
