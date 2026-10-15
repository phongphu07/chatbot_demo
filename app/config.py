import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

def reload_env():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)

class Settings:
    PROJECT_NAME: str = "Multi-Purpose AI Assistant (3-in-1)"
    VERSION: str = "1.0.0"
    
    @property
    def LLM_PROVIDER(self) -> str:
        reload_env()
        return os.getenv("LLM_PROVIDER", "gemini").lower()
    
    @LLM_PROVIDER.setter
    def LLM_PROVIDER(self, val: str):
        if val:
            os.environ["LLM_PROVIDER"] = val.lower()
    
    @property
    def GEMINI_API_KEY(self) -> str:
        reload_env()
        return os.getenv("GEMINI_API_KEY", "").strip()
    
    @GEMINI_API_KEY.setter
    def GEMINI_API_KEY(self, val: str):
        if val is not None:
            os.environ["GEMINI_API_KEY"] = val.strip()
    
    @property
    def OPENAI_API_KEY(self) -> str:
        reload_env()
        return os.getenv("OPENAI_API_KEY", "").strip()
    
    @OPENAI_API_KEY.setter
    def OPENAI_API_KEY(self, val: str):
        if val is not None:
            os.environ["OPENAI_API_KEY"] = val.strip()
    
    @property
    def GEMINI_MODEL(self) -> str:
        reload_env()
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    @property
    def OPENAI_MODEL(self) -> str:
        reload_env()
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    @property
    def EMBEDDING_PROVIDER(self) -> str:
        reload_env()
        return os.getenv("EMBEDDING_PROVIDER", "gemini").lower()
    
    @EMBEDDING_PROVIDER.setter
    def EMBEDDING_PROVIDER(self, val: str):
        if val:
            os.environ["EMBEDDING_PROVIDER"] = val.lower()
    
    # Dimensions mapping
    EMBEDDING_DIMENSIONS = {
        "gemini": 768,       # text-embedding-004
        "openai": 1536,     # text-embedding-3-small
        "local": 384        # all-MiniLM-L6-v2
    }
    
    @property
    def embedding_dim(self) -> int:
        return self.EMBEDDING_DIMENSIONS.get(self.EMBEDDING_PROVIDER, 768)

    # Chunking defaults
    @property
    def DEFAULT_CHUNK_SIZE(self) -> int:
        reload_env()
        return int(os.getenv("DEFAULT_CHUNK_SIZE", "600"))

    @property
    def DEFAULT_CHUNK_OVERLAP(self) -> int:
        reload_env()
        return int(os.getenv("DEFAULT_CHUNK_OVERLAP", "120"))
    
    # Database (PostgreSQL + pgvector)
    @property
    def POSTGRES_HOST(self) -> str:
        reload_env()
        return os.getenv("POSTGRES_HOST", "localhost")

    @property
    def POSTGRES_PORT(self) -> int:
        reload_env()
        return int(os.getenv("POSTGRES_PORT", "5432"))

    @property
    def POSTGRES_DB(self) -> str:
        reload_env()
        return os.getenv("POSTGRES_DB", "chatbot_db")

    @property
    def POSTGRES_USER(self) -> str:
        reload_env()
        return os.getenv("POSTGRES_USER", "postgres")

    @property
    def POSTGRES_PASSWORD(self) -> str:
        reload_env()
        return os.getenv("POSTGRES_PASSWORD", "postgrespassword")
    
    @property
    def postgres_dsn(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    PORT: int = 8000

settings = Settings()
