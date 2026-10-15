import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from pypdf import PdfReader

class TextChunker:
    """
    Engine băm nhỏ văn bản (Chunking) chuyên dụng cho RAG & Vector Database:
    - Recursive splitting (đoạn -> dòng -> câu -> từ).
    - Overlap thông minh tránh đứt gãy ý nghĩa.
    - Contextual Prefixing (Anthropic style): đính kèm tiêu đề ngữ cảnh vào từng chunk.
    - Trích xuất metadata phong phú.
    """

    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 120,
        separators: Optional[List[str]] = None,
        add_contextual_header: bool = True
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", "? ", "! ", " ", ""]
        self.add_contextual_header = add_contextual_header

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Tách văn bản đệ quy theo danh sách phân tách"""
        final_chunks = []
        separator = separators[-1]
        new_separators = []

        for i, sep in enumerate(separators):
            if sep == "":
                separator = ""
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1:]
                break

        splits = text.split(separator) if separator else list(text)

        good_splits = []
        for s in splits:
            if not s.strip():
                continue
            if len(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if new_separators:
                    other_info = self._split_text(s, new_separators)
                    good_splits.extend(other_info)
                else:
                    good_splits.append(s)

        # Hợp nhất các split nhỏ lại sao cho vừa chunk_size và có overlap
        current_chunk = []
        current_len = 0

        for piece in good_splits:
            piece_len = len(piece)
            if current_len + piece_len + (len(separator) if current_chunk else 0) > self.chunk_size:
                if current_chunk:
                    joined = separator.join(current_chunk).strip()
                    if joined:
                        final_chunks.append(joined)
                    
                    # Giữ lại phần overlap cho chunk tiếp theo
                    overlap_chunks = []
                    overlap_len = 0
                    for prev_piece in reversed(current_chunk):
                        if overlap_len + len(prev_piece) <= self.chunk_overlap:
                            overlap_chunks.insert(0, prev_piece)
                            overlap_len += len(prev_piece)
                        else:
                            break
                    current_chunk = overlap_chunks
                    current_len = overlap_len

            current_chunk.append(piece)
            current_len += piece_len + (len(separator) if len(current_chunk) > 1 else 0)

        if current_chunk:
            joined = separator.join(current_chunk).strip()
            if joined:
                final_chunks.append(joined)

        return final_chunks

    def chunk_document(
        self,
        text: str,
        doc_name: str,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Băm tài liệu thành danh sách các chunk có cấu trúc chuẩn:
        - content: nội dung thuần túy của chunk
        - contextual_content: nội dung có tiền tố ngữ cảnh (dùng để sinh vector embedding)
        - metadata: thông tin chi tiết
        """
        # Làm sạch văn bản cơ bản
        cleaned_text = re.sub(r"\r\n", "\n", text)
        cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

        if not cleaned_text:
            return []

        raw_chunks = self._split_text(cleaned_text, self.separators)
        total_chunks = len(raw_chunks)
        results = []

        for i, chunk_text in enumerate(raw_chunks, start=1):
            # Mẹo Contextual Retrieval: gắn tiêu đề tài liệu & số đoạn vào trước khi embed
            if self.add_contextual_header:
                contextual_content = f"[Tài liệu: {doc_name} | Đoạn {i}/{total_chunks}]\n{chunk_text}"
            else:
                contextual_content = chunk_text

            chunk_meta = {
                "doc_name": doc_name,
                "chunk_index": i,
                "total_chunks": total_chunks,
                "char_count": len(chunk_text),
                **(extra_metadata or {})
            }

            results.append({
                "doc_name": doc_name,
                "chunk_index": i,
                "content": chunk_text,
                "contextual_content": contextual_content,
                "metadata": chunk_meta
            })

        return results

    @staticmethod
    def extract_text_from_file(file_path: Path) -> str:
        """Trích xuất text từ file txt, md hoặc pdf"""
        suffix = file_path.suffix.lower()
        if suffix in [".txt", ".md", ".json", ".csv"]:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        elif suffix == ".pdf":
            reader = PdfReader(str(file_path))
            pages_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(f"--- Trang {i+1} ---\n{text}")
            return "\n\n".join(pages_text)
        else:
            raise ValueError(f"Định dạng file không hỗ trợ: {suffix}. Chỉ hỗ trợ .txt, .md, .pdf")
