# ADR-005: Ligação entre Anatel e Receita por chave exata

**Status:** aceito · **Data:** 2026-10-31

## Contexto

O plano previa ligar as empresas da Anatel aos CNPJs com chave exata quando houvesse CNPJ e, quando faltasse ou divergisse, com similaridade de razão social mais município. Também previa rotular 200 pares à mão para medir precisão e revocação.

A medição com dados reais, em 2026-09, mudou esse cenário:

| Medida | Resultado |
| --- | --- |
| Linhas da Anatel sem CNPJ | 0 de 56,2 milhões |
| CNPJs da Anatel encontrados na Receita pela chave completa | 19.202 de 19.202 |
| Acessos cobertos | 58.075.574 de 58.075.574 (100%) |

## Decisão

- **Usar só a chave exata.** Similaridade de nomes não teria nenhum caso para resolver, e só poderia introduzir falsos positivos.
- **Não rotular os 200 pares nesta fase.** Com todos os casos resolvidos pela chave, a precisão seria uma medida vazia.
- **Manter o filtro por CNAE somado aos CNPJs da Anatel.** Os dois CNAEs citados no plano (6110-8/03 e 6190-6/01) cobrem 18.166 de 19.162 raízes de CNPJ (94,8%), o equivalente a 99,96% dos acessos. Sem a união, cerca de mil provedores pequenos ficariam de fora.
- **Manter union-find e similaridade de strings.** Eles serão usados na Fase 2, na resolução de sócios, em que a Receita mascara parte do CPF e não existe chave exata. A rotulagem manual muda para lá.

## Consequências

- Esse resultado vale para a ligação entre empresas, não para sócios.
- Se a Anatel passar a publicar linhas sem CNPJ, o contrato pandera interrompe o pipeline, e esta decisão precisa ser revista.
