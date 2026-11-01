"""Gera docs/data-dictionary.md a partir do manifesto do dbt."""

import json
from pathlib import Path
from typing import Any

SEMANTIC_SCHEMA = "semantic"


def semantic_models(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    models = [
        node
        for node in manifest["nodes"].values()
        if node["resource_type"] == "model" and node["schema"] == SEMANTIC_SCHEMA
    ]
    return sorted(models, key=lambda node: node["name"])


def render(models: list[dict[str, Any]]) -> str:
    lines = [
        "# Dicionário de dados",
        "",
        "Gerado por `make transform` a partir de `dbt/models/semantic/schema.yml`. Não edite.",
        "",
        "O schema `semantic` é a única parte do banco que o agente enxerga.",
    ]
    for model in models:
        lines += ["", f"## `{model['schema']}.{model['name']}`", "", model["description"].strip()]
        lines += ["", "| Coluna | Descrição |", "| --- | --- |"]
        for column in model["columns"].values():
            description = " ".join(column["description"].split())
            lines.append(f"| `{column['name']}` | {description} |")
    return "\n".join(lines) + "\n"


def write(manifest_path: Path, target: Path) -> None:
    manifest = json.loads(manifest_path.read_text())
    target.write_text(render(semantic_models(manifest)))
