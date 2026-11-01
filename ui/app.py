"""Tela de demonstração: pergunta, resposta, consultas e tempo de cada passo."""

import os
from typing import Any

import httpx
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8010")
EXAMPLES = [
    "Quantos acessos de banda larga existem em Anápolis?",
    "Quais são os 3 maiores provedores de Catalão?",
    "Quantos municípios de Goiás têm mercado altamente concentrado?",
]
REQUEST_TIMEOUT = 300


def ask(question: str) -> dict[str, Any]:
    response = httpx.post(f"{API_URL}/ask", json={"question": question}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    return payload


def show_steps(steps: list[dict[str, Any]]) -> None:
    for number, step in enumerate(steps, start=1):
        name = step["tool"] or "modelo"
        status = f"erro: {step['error']}" if step["error"] else "ok"
        st.markdown(f"**{number}. {name}**, {step['seconds']:.2f} s, {status}")


st.set_page_config(page_title="Analista de Mercado Telecom", page_icon="📡")
st.title("Analista de Mercado Telecom")
st.caption("Banda larga fixa no Brasil, com dados públicos da Anatel, da Receita e do IBGE.")

question = st.text_input("Sua pergunta", placeholder=EXAMPLES[0], max_chars=500)
st.caption("Exemplos: " + " · ".join(EXAMPLES))

if st.button("Perguntar", type="primary", disabled=not question):
    with st.spinner("Consultando os dados..."):
        try:
            result = ask(question)
        except httpx.HTTPError as error:
            st.error(f"Não foi possível consultar o agente: {error}")
            st.stop()

    st.markdown(result["answer"])
    if result["verified"]:
        st.success("Cada número da resposta foi encontrado nos resultados das consultas.")
    else:
        st.warning("Alguns números não foram encontrados nos resultados das consultas.")

    st.subheader("Consultas usadas")
    for query in result["queries"]:
        st.code(query, language="sql")
    st.subheader(f"Passos ({result['seconds']:.1f} s)")
    show_steps(result["steps"])
