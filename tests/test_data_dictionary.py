from telecom_analyst.etl.data_dictionary import render, semantic_models


def test_includes_only_semantic_models_in_name_order() -> None:
    def node(name: str, schema: str) -> dict[str, object]:
        return {"resource_type": "model", "name": name, "schema": schema}

    manifest = {
        "nodes": {
            "a": node("zeta", "semantic"),
            "b": node("alfa", "semantic"),
            "c": node("fato", "marts"),
            "d": {"resource_type": "test", "name": "teste", "schema": "semantic"},
        }
    }

    assert [model["name"] for model in semantic_models(manifest)] == ["alfa", "zeta"]


def test_render_flattens_multiline_descriptions() -> None:
    model = {
        "schema": "semantic",
        "name": "mercado",
        "description": "Um município.\n",
        "columns": {"hhi": {"name": "hhi", "description": "Faixa do\n  CADE."}},
    }

    text = render([model])

    assert "## `semantic.mercado`" in text
    assert "| `hhi` | Faixa do CADE. |" in text
