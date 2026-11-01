"""Similaridade de strings e normalização de razões sociais."""

import re
import unicodedata

PREFIX_WEIGHT = 0.1
MAX_PREFIX = 4
MIN_SCORE_FOR_PREFIX_BONUS = 0.7
TRIGRAM_SIZE = 3

# Formas societárias e palavras genéricas que aproximam empresas sem relação entre si.
COMPANY_NOISE = frozenset(
    {
        "COMERCIO",
        "EIRELI",
        "EPP",
        "LTDA",
        "ME",
        "MEI",
        "SA",
        "SERVICOS",
        "TELECOM",
        "TELECOMUNICACOES",
    }
)


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize_company_name(name: str) -> str:
    """Reduz a razão social às palavras que de fato distinguem a empresa."""
    upper = strip_accents(name).upper().replace("S/A", "SA").replace("S.A.", "SA")
    words = re.sub(r"[^A-Z0-9 ]", " ", upper).split()
    return " ".join(word for word in words if word not in COMPANY_NOISE)


def jaro(first: str, second: str) -> float:
    """Similaridade de Jaro entre 0 e 1, baseada em caracteres próximos e transposições."""
    if first == second:
        return 1.0
    if not first or not second:
        return 0.0

    window = max(max(len(first), len(second)) // 2 - 1, 0)
    first_matched = [False] * len(first)
    second_matched = [False] * len(second)
    matches = 0
    for index, char in enumerate(first):
        start = max(index - window, 0)
        stop = min(index + window + 1, len(second))
        for other in range(start, stop):
            if not second_matched[other] and second[other] == char:
                first_matched[index] = second_matched[other] = True
                matches += 1
                break
    if matches == 0:
        return 0.0

    first_chars = [char for char, hit in zip(first, first_matched, strict=True) if hit]
    second_chars = [char for char, hit in zip(second, second_matched, strict=True) if hit]
    # Divisão inteira, como no strcmp95 de Winkler. A fórmula usual sugere fração, mas diverge.
    transpositions = sum(a != b for a, b in zip(first_chars, second_chars, strict=True)) // 2
    return (matches / len(first) + matches / len(second) + (matches - transpositions) / matches) / 3


def jaro_winkler(first: str, second: str) -> float:
    """Jaro com bônus para prefixo comum, onde costumam estar as partes mais estáveis do nome."""
    score = jaro(first, second)
    if score <= MIN_SCORE_FOR_PREFIX_BONUS:
        return score
    prefix = 0
    for a, b in zip(first[:MAX_PREFIX], second[:MAX_PREFIX], strict=False):
        if a != b:
            break
        prefix += 1
    return score + prefix * PREFIX_WEIGHT * (1 - score)


def trigrams(text: str) -> frozenset[str]:
    padded = f"  {text} "
    return frozenset(
        padded[index : index + TRIGRAM_SIZE] for index in range(len(padded) - TRIGRAM_SIZE + 1)
    )


def trigram_similarity(first: str, second: str) -> float:
    """Jaccard dos trigramas. Tolera palavras trocadas de ordem, ao contrário do Jaro."""
    if first == second:
        return 1.0
    if not first or not second:
        return 0.0
    first_set, second_set = trigrams(first), trigrams(second)
    return len(first_set & second_set) / len(first_set | second_set)
