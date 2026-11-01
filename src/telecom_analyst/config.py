"""Configuração do projeto, lida do ambiente e do arquivo .env."""

from pathlib import Path

from psycopg.conninfo import make_conninfo
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5433

    mlflow_port: int = 5000

    langfuse_port: int = 3001
    langfuse_public_key: str
    langfuse_secret_key: SecretStr

    data_dir: Path = Path("data")

    @property
    def postgres_conninfo(self) -> str:
        return make_conninfo(
            host=self.postgres_host,
            port=self.postgres_port,
            dbname=self.postgres_db,
            user=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
        )

    @property
    def mlflow_url(self) -> str:
        return f"http://localhost:{self.mlflow_port}"

    @property
    def langfuse_url(self) -> str:
        return f"http://localhost:{self.langfuse_port}"
