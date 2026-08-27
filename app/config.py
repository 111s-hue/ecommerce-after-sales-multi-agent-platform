from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LangGraph 电商售后多智能体平台"
    app_version: str = "1.0.0"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]
    request_id_header: str = "X-Request-ID"
    database_url: str = "sqlite:///./data/mysystem.db"
    seed_demo_data: bool = True
    redis_url: str = "redis://localhost:6379"
    use_redis_checkpoint: bool = False
    tool_transport: str = "local"
    mcp_server_url: str = "http://localhost:8002/mcp"
    mcp_server_host: str = "127.0.0.1"
    mcp_server_port: int = 8002

    llm_base_url: str = "http://localhost:8001/v1"
    llm_api_key: str = "EMPTY"
    llm_model: str = "Qwen/Qwen3-8B-Instruct"
    llm_enabled: bool = False
    llm_timeout_seconds: float = 30
    max_agent_steps: int = 3

    rag_backend: str = "hybrid-lite"
    rag_top_k: int = 4
    bge_model: str = "BAAI/bge-m3"
    policy_dir: Path = Path("./data/policies")
    faiss_index_dir: Path = Path("./data/indexes")
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = "root:Milvus"
    milvus_collection: str = "after_sales_policies"
    knowledge_tenant_id: str = "demo"
    evaluation_report_path: Path = Path("./data/evaluation/latest.json")
    max_knowledge_upload_bytes: int = 2 * 1024 * 1024

    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_enabled: bool = False
    minio_bucket: str = "after-sales-kb"

    auth_enabled: bool = True
    jwt_secret: str = "change-this-32-byte-secret-in-production"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "after-sales-platform"
    jwt_audience: str = "after-sales-console"
    default_tenant_code: str = "community"
    access_token_minutes: int = 120
    allowed_hosts: list[str] = ["127.0.0.1", "localhost", "testserver", "10.2.0.2"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def validate_for_startup(self) -> None:
        if self.environment != "production":
            return
        errors: list[str] = []
        if not self.auth_enabled:
            errors.append("AUTH_ENABLED must be true")
        if self.seed_demo_data:
            errors.append("SEED_DEMO_DATA must be false")
        if (
            self.jwt_secret == "change-this-32-byte-secret-in-production"
            or len(self.jwt_secret) < 32
        ):
            errors.append("JWT_SECRET must be replaced with at least 32 random bytes")
        if self.database_url.startswith("sqlite"):
            errors.append("DATABASE_URL must use MySQL or PostgreSQL in production")
        if "*" in self.allowed_hosts:
            errors.append("ALLOWED_HOSTS must not contain a wildcard")
        if "*" in self.cors_origins:
            errors.append("CORS_ORIGINS must not contain a wildcard")
        if self.access_token_minutes > 60:
            errors.append("ACCESS_TOKEN_MINUTES must be 60 or less in production")
        if self.minio_enabled and (
            self.minio_access_key == "minioadmin" or self.minio_secret_key == "minioadmin"
        ):
            errors.append("MinIO default credentials must be replaced")
        if errors:
            raise RuntimeError("Invalid production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()
