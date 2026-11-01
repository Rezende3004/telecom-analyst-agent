# Jaro-Winkler próprio contra rapidfuzz

Compara `algorithms/string_similarity.py` com o rapidfuzz em 200 mil pares aleatórios de nomes de provedores da Anatel.

| Medida | Resultado |
| --- | --- |
| Pares com nota diferente | 0 de 200.000 |
| Tempo da implementação própria | 2,15 s |
| Tempo do rapidfuzz | 0,07 s, 31 vezes mais rápido |

A comparação encontrou dois erros que os valores de referência da literatura não exercitavam: 64.691 pares divergiam. A contagem de transposições usava divisão real, e o bônus de prefixo não respeitava o limite de 0,7. O projeto segue o `strcmp95` de Winkler, a mesma regra do rapidfuzz.

Python puro contra C++ explica a diferença de velocidade. Em produção, o rapidfuzz é a escolha certa para grandes volumes. A versão própria existe para demonstrar o algoritmo.

```bash
uv run --group benchmark python benchmarks/string_similarity/run.py data/staging/anatel/acessos
```
