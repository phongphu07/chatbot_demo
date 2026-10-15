import time
import threading
from typing import Dict, Any, Optional

class QueryCache:
    """
    Bộ nhớ đệm hiệu năng cao (In-Memory High Performance Cache with TTL).
    Hỗ trợ giảm độ trễ truy vấn xuống < 2ms và bảo vệ hạn ngạch (Rate Limit) của LLM/Embeddings
    khi có hàng nghìn nhân viên cùng hỏi các câu hỏi phổ biến.
    """
    def __init__(self, default_ttl: int = 300, max_entries: int = 5000):
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _normalize_key(self, key: str) -> str:
        return " ".join(key.strip().lower().split())

    def get(self, key: str) -> Optional[Any]:
        norm_key = self._normalize_key(key)
        now = time.time()
        with self._lock:
            entry = self._store.get(norm_key)
            if not entry:
                self.misses += 1
                return None
            if now > entry["expires_at"]:
                del self._store[norm_key]
                self.misses += 1
                return None
            self.hits += 1
            return entry["data"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        norm_key = self._normalize_key(key)
        actual_ttl = ttl if ttl is not None else self.default_ttl
        now = time.time()
        with self._lock:
            if len(self._store) >= self.max_entries:
                # Dọn dẹp 10% bản ghi cũ nhất
                sorted_keys = sorted(self._store.keys(), key=lambda k: self._store[k]["expires_at"])
                for k in sorted_keys[: max(10, self.max_entries // 10)]:
                    self._store.pop(k, None)
            self._store[norm_key] = {
                "data": value,
                "expires_at": now + actual_ttl
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            hit_ratio = round((self.hits / total * 100), 1) if total > 0 else 0.0
            return {
                "cached_items": len(self._store),
                "hits": self.hits,
                "misses": self.misses,
                "hit_ratio_percent": hit_ratio
            }

    def clear(self):
        with self._lock:
            self._store.clear()

# Cache dùng chung cho Embeddings và Kết quả tìm kiếm RAG
rag_cache = QueryCache(default_ttl=600)
