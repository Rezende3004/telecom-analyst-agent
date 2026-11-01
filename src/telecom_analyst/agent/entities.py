"""Detecta municípios homônimos na pergunta, antes de o modelo escrever a SQL."""

import re
from collections import defaultdict
from collections.abc import Iterable

from telecom_analyst.algorithms.string_similarity import strip_accents


def _fold(text: str) -> str:
    return strip_accents(text).casefold()


class HomonymIndex:
    """Avisa quando a pergunta cita uma cidade que existe em mais de um estado."""

    def __init__(self, municipalities: Iterable[tuple[str, str, str]]) -> None:
        states: defaultdict[str, set[str]] = defaultdict(set)
        self._state_names: set[str] = set()
        self._state_codes: set[str] = set()
        for name, code, state_name in municipalities:
            states[name].add(code)
            self._state_names.add(_fold(state_name))
            self._state_codes.add(code)
        self._homonyms = {name: sorted(codes) for name, codes in states.items() if len(codes) > 1}
        self._patterns = {
            name: re.compile(rf"\b{re.escape(_fold(name))}\b") for name in self._homonyms
        }

    def _mentions_state(self, question: str) -> bool:
        folded = _fold(question)
        if any(state in folded for state in self._state_names):
            return True
        return any(re.search(rf"\b{code}\b", question) for code in self._state_codes)

    def note(self, question: str) -> str | None:
        """Devolve o aviso para o modelo, ou None se não houver ambiguidade."""
        if self._mentions_state(question):
            return None
        folded = _fold(question)
        found = [name for name, pattern in self._patterns.items() if pattern.search(folded)]
        if not found:
            return None
        name = max(found, key=len)
        states = ", ".join(self._homonyms[name])
        return (
            f"Atenção: existe mais de um município chamado {name} ({states}) e a pergunta não "
            "diz qual. Selecione a coluna `uf`, traga todos e cite as UFs na resposta."
        )
