from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # API Keys
    groq_api_key:        str
    pinecone_api_key:    str
    pinecone_index_name: str = "wanderrag-tourism"

    # Database
    # Local:      sqlite:///./data/app.db
    # Production: automatically set by Render PostgreSQL addon
    database_url: str = "sqlite:///./data/app.db"

    # Embedding
    embedding_model:     str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # LLM
    groq_model: str = "llama-3.1-8b-instant"

    # App
    app_env:     str = "development"
    app_name:    str = "WanderRAG"
    app_version: str = "1.0.0"

    class Config:
        env_file = ".env"
        extra    = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()