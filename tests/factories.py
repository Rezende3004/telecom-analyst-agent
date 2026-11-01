from pathlib import Path
from typing import Any

from telecom_analyst.config import Settings


def make_settings(data_dir: Path = Path("data"), **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "postgres_user": "user",
        "postgres_password": "secret",
        "postgres_db": "db",
        "langfuse_public_key": "pk",
        "langfuse_secret_key": "sk",
        "data_dir": data_dir,
        "duckdb_memory_limit": "1GB",
    }
    return Settings(_env_file=None, **(values | overrides))
