"""Compara o Jaro-Winkler próprio com o rapidfuzz em nomes reais de provedores."""

import random
import sys
import time
from pathlib import Path

import polars as pl
from rapidfuzz.distance import JaroWinkler

from telecom_analyst.algorithms.string_similarity import jaro_winkler, normalize_company_name

PAIRS = 200_000
TOLERANCE = 1e-9


def main(acessos: Path) -> None:
    names = (
        pl.scan_parquet(acessos / "*" / "*.parquet", hive_partitioning=False)
        .select("empresa")
        .unique()
        .collect()["empresa"]
        .drop_nulls()
        .to_list()
    )
    normalized = [normalize_company_name(name) for name in names]
    rng = random.Random(42)  # noqa: S311
    pairs = [(rng.choice(normalized), rng.choice(normalized)) for _ in range(PAIRS)]

    started = time.perf_counter()
    own = [jaro_winkler(first, second) for first, second in pairs]
    own_seconds = time.perf_counter() - started

    started = time.perf_counter()
    library = [JaroWinkler.similarity(first, second) for first, second in pairs]
    library_seconds = time.perf_counter() - started

    different = sum(abs(a - b) > TOLERANCE for a, b in zip(own, library, strict=True))
    print(f"nomes: {len(names)}, pares: {PAIRS}")
    print(f"próprio: {own_seconds:.2f} s, rapidfuzz: {library_seconds:.2f} s")
    print(f"razão: {own_seconds / library_seconds:.0f} vezes")
    print(f"pares com nota diferente: {different}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
