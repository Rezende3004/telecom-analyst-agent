import psycopg.conninfo
import pytest
from pydantic import ValidationError

from telecom_analyst.config import Settings
from tests.factories import make_settings


def test_conninfo_keeps_special_characters_in_password() -> None:
    password = "p@ss w'rd/1"  # noqa: S105
    settings = make_settings(postgres_password=password)

    parsed = psycopg.conninfo.conninfo_to_dict(settings.postgres_conninfo)

    assert parsed["password"] == password
    assert parsed["port"] == "5433"


def test_secrets_stay_out_of_repr() -> None:
    settings = make_settings(postgres_password="visible-if-leaked")  # noqa: S106

    assert "visible-if-leaked" not in repr(settings)


def test_missing_required_setting_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POSTGRES_USER", raising=False)

    with pytest.raises(ValidationError, match="postgres_user"):
        Settings(_env_file=None)  # type: ignore[call-arg]
