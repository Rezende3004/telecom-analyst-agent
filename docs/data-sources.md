# Fontes de dados

Peculiaridades reais de cada fonte, verificadas nos arquivos. Os dados não vão para o git: `make ingest` baixa tudo em `data/raw/` e grava um `manifest.json` por fonte, com URL, SHA-256, ETag, data do download e período de referência.

Volumes do arquivo de 30/10/2026, com dados até 2026-09.

## Anatel: acessos de banda larga fixa

**Origem:** `acessos_banda_larga_fixa.zip`, nos dados abertos da Anatel (1,07 GB compactado).

| Arquivos no zip | Uso |
| --- | --- |
| `Acessos_Banda_Larga_Fixa_<período>.csv` | **série usada**: uma linha por combinação, 56,2 milhões de linhas |
| `..._Colunas.csv` | ignorados: os mesmos dados com um mês por coluna |
| `..._Total.csv` | total nacional mensal, usado para conciliar a ingestão |
| `Densidade_Banda_Larga_Fixa.csv` | densidade publicada; ver a ressalva abaixo |

### O que muda ao longo da série

- **Dois layouts.** Até 2020 são 13 colunas. Desde 2021 entram `Velocidade`, `Tipo de Pessoa` e `Tipo de Produto`. Um layout diferente desses dois interrompe a ingestão.
- **Granularidade.** As linhas por ano triplicam em 2021 por causa das colunas novas; isso não é crescimento do mercado.
- **Periodicidade.** De 2007 a 2010 os dados são trimestrais. A partir de 2011, mensais.
- **Tecnologias.** Os nomes mudam: `xDSL` e `Fibra` vão até 2020, e depois aparecem `ADSL1`, `ADSL2`, `FTTH` e `FTTB`. Tecnologia nova não interrompe o pipeline. Para comparar anos, use `meio_acesso`, que é estável.
- **Faixas de velocidade.** Quatro das oito faixas só existem em parte da série, então comparações longas precisam agrupar faixas.

### Armadilhas

- **A chave não é única.** 2,1 milhões de combinações de ano, mês, CNPJ, município, tecnologia, meio, faixa, velocidade, tipo de pessoa e tipo de produto aparecem em mais de uma linha. Some as linhas; nunca deduplique. O total oficial só bate somando todas.
- **`grupo_economico` muda com o tempo.** O CNPJ `11159733000190` alterna entre `ALARES` e `IPNET TELECOM`/`OUTROS`, até voltando atrás. Não existe um grupo fixo por CNPJ.
- **`OUTROS` concentra 40% dos acessos.** Em 2026-09 são 23,4 milhões de 58,1 milhões, em mais de 19 mil CNPJs. É a lacuna que o grafo de sócios da Fase 2 ataca.
- **Cadastro ausente.** Esse mesmo CNPJ vem sem empresa, grupo e porte em 540 linhas de 2026-01 a 2026-03. As linhas ficam, porque o total oficial conta esses acessos.
- **`velocidade_mbps` tem erros de declaração.** Há valores de até 27,8 bilhões de Mbps, enquanto a mediana de 2026 é 100. Não use médias sem tratar; a faixa de velocidade é mais confiável.
- **Nome de empresa pode conter nome de pessoa.** Empresários individuais aparecem como `FULANO DE TAL - ME`. Isso importa para a decisão de LGPD da Fase 2.

### A densidade publicada usa população, não domicílios

A metodologia da Anatel (`Densidades.pdf`) define a densidade como acessos por 100 domicílios. Os valores publicados em 2026-09, porém, são acessos por 100 **habitantes**, usando a estimativa de população de 2026 do IBGE:

| Teste em 2026-09 | Municípios que casam (diferença < 0,01) |
| --- | --- |
| acessos / população × 100 | 5.571 de 5.571 |
| acessos / domicílios × 100 | 0 de 5.571 |

Goiânia, por exemplo, tem densidade publicada de 36,5, que é 551.414 acessos sobre 1.511.709 habitantes. Por domicílio, são 100,4. O projeto calcula a própria penetração por domicílio em vez de reaproveitar esse campo.

### Controles da ingestão

| Controle | Resultado em 2026-09 |
| --- | --- |
| Soma mensal contra `Total.csv` | 205 de 205 meses idênticos |
| Códigos de município presentes no IBGE | 5.571 de 5.571 |
| UF da Anatel igual à UF do IBGE | sem divergências |
| Tempo de `make ingest`, com o zip já baixado | cerca de 1 minuto |
| Parquet em `data/staging/anatel` | 521 MB |

## IBGE

Os dados vêm das APIs de Localidades e de Agregados (SIDRA), e o código de município é a chave.

| Campo | Tabela SIDRA | Variável | Período atual |
| --- | --- | --- | --- |
| `populacao` | 6579, Estimativas de População | 9324 | 2026 |
| `domicilios` | 4712, Censo Demográfico | 381 | 2022 |
| `pib_mil_reais` | 5938, PIB dos Municípios | 37 | 2023 |
| `renda_per_capita` | 10295, Censo Demográfico | 13431 | 2022 |

- **Os períodos são diferentes.** Cada indicador tem seu ano, gravado ao lado do valor. `domicilios` é de 2022, então qualquer penetração em 2026 compara acessos atuais com domicílios de quatro anos atrás. Valores acima de 100 são esperados.
- **Boa Esperança do Norte (MT)** foi criado depois do Censo 2022, por isso não tem domicílios, PIB nem renda. O contrato tolera esse único caso, e dois municípios sem censo interrompem o pipeline.

## Receita Federal: base do CNPJ

**Origem:** compartilhamento Nextcloud público da Receita, em `Dados/Cadastros/CNPJ/AAAA-MM/`, com acesso por WebDAV. A URL antiga deixou de responder.

| Medida em 2026-10 | Valor |
| --- | --- |
| Arquivos usados | 35 zips, 7,0 GB |
| Descompactado | 24 GB |
| Estabelecimentos na base | 73,8 milhões |
| Recorte de telecom | 694.713 estabelecimentos e 597.401 empresas |
| Parquet do recorte | 37 MB |

- **Codificação.** Os arquivos são latin-1, sem cabeçalho, e têm bytes de controle soltos, como `0x1A` e `0x8F`. A extração converte para UTF-8 e troca esses bytes por espaço.
- **Quebras de linha em campos.** Sete campos entre aspas têm quebra de linha, por isso há 7 registros a menos que linhas no arquivo.
- **CNPJ alfanumérico.** Desde julho de 2026 a Receita emite CNPJ com letras. O projeto trata CNPJ sempre como texto.
- **Município da Receita não é o código do IBGE.** O campo usa o código TOM, com 4 dígitos. O projeto usa a UF da matriz e não faz essa ligação.
- **Dados pessoais.** A razão social de MEIs inclui o CPF completo. O tratamento está no [ADR-003](adr/003-dados-pessoais.md).
- **Ligação com a Anatel.** A chave exata de CNPJ resolve 100% dos casos. Ver o [ADR-005](adr/005-ligacao-anatel-receita.md).
