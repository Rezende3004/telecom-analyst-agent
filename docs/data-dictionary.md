# Dicionário de dados

Gerado por `make transform` a partir de `dbt/models/semantic/schema.yml`. Não edite.

O schema `semantic` é a única parte do banco que o agente enxerga.

## `semantic.acessos_mensais`

Acessos por mês, provedor, município, meio de acesso e tipo de pessoa, com 16 milhões de linhas. Sempre filtre por período. Sempre use SUM(acessos): nunca conte linhas.

| Coluna | Descrição |
| --- | --- |
| `mes_referencia` | Primeiro dia do mês. De 2007 a 2010 a série é trimestral. |
| `municipio` | Nome do município. |
| `uf` | Sigla da unidade da federação. |
| `regiao` | Grande região. |
| `municipio_ibge` | Código do IBGE com 7 dígitos. |
| `cnpj` | CNPJ do provedor. |
| `provedor` | Nome público do provedor. |
| `grupo_economico` | Grupo mais recente, aplicado a toda a série para comparar períodos. |
| `agente_economico` | Identificador do grupo, ou a raiz do CNPJ quando não há grupo. |
| `agente_nome` | Nome legível do agente econômico. Use este nome nas respostas. |
| `meio_acesso` | Fibra, Cabo Coaxial, Cabo Metálico, Rádio, Satélite ou outros. |
| `tipo_pessoa` | Pessoa Física, Pessoa Jurídica ou Não Informado. Antes de 2021 é Não Informado. |
| `acessos` | Acessos em serviço. |

## `semantic.mercado_municipal`

Um município por mês, com as métricas já calculadas. É a primeira opção para perguntas de concentração, penetração e crescimento.

| Coluna | Descrição |
| --- | --- |
| `mes_referencia` | Primeiro dia do mês. |
| `municipio` | Nome do município. |
| `uf` | Sigla da unidade da federação. |
| `regiao` | Grande região. |
| `municipio_ibge` | Código do IBGE com 7 dígitos. |
| `populacao` | População estimada mais recente. |
| `domicilios` | Domicílios do Censo 2022. |
| `renda_per_capita` | Renda domiciliar per capita do Censo 2022, em reais. |
| `acessos` | Total de acessos no município. |
| `acessos_pessoa_fisica` | Acessos de pessoas físicas. Nulo antes de 2021. |
| `penetracao_domicilios` | Todos os acessos por 100 domicílios. Pode passar de 100. |
| `penetracao_residencial` | Acessos de pessoas físicas por 100 domicílios. Nulo antes de 2021. |
| `provedores` | Agentes econômicos com acessos no município. |
| `lider` | Nome do agente econômico com mais acessos. |
| `lider_agente_economico` | Identificador do líder, igual a `agente_economico` nas outras views. |
| `share_lider_pct` | Market share do líder, em pontos percentuais. |
| `hhi` | Índice Herfindahl-Hirschman, de 0 a 10.000, por agente econômico. |
| `nivel_concentracao` | Faixa do Guia H do CADE: não concentrado (HHI abaixo de 1.500), moderadamente concentrado (1.500 a 2.500) ou altamente concentrado (acima de 2.500). Um mercado pouco disputado é um mercado altamente concentrado. |
| `crescimento_12m_pct` | Variação dos acessos contra o mesmo mês do ano anterior. Nulo se esse mês não existir. |

## `semantic.municipios`

Um município por linha. Use para filtrar por população, renda, UF ou região.

| Coluna | Descrição |
| --- | --- |
| `municipio_ibge` | Código do IBGE com 7 dígitos. |
| `municipio` | Nome do município com acentos. |
| `uf` | Sigla da unidade da federação. |
| `uf_nome` | Nome da unidade da federação. |
| `regiao` | Grande região, como Centro-Oeste. |
| `populacao` | População estimada no ano de `populacao_ano`. |
| `populacao_ano` | Ano da estimativa de população. |
| `domicilios` | Domicílios particulares permanentes ocupados. Nulo em município criado depois do Censo. |
| `domicilios_ano` | Ano do censo que deu origem a `domicilios`. |
| `pib_mil_reais` | PIB municipal em milhares de reais. |
| `pib_ano` | Ano do PIB. |
| `renda_per_capita` | Rendimento nominal médio mensal domiciliar per capita, em reais. |
| `renda_ano` | Ano do censo que deu origem à renda. |

## `semantic.participacao_provedores`

Market share de cada agente econômico por município e mês.

| Coluna | Descrição |
| --- | --- |
| `mes_referencia` | Primeiro dia do mês. |
| `municipio` | Nome do município. |
| `uf` | Sigla da unidade da federação. |
| `regiao` | Grande região. |
| `municipio_ibge` | Código do IBGE com 7 dígitos. |
| `agente_economico` | Identificador do grupo, ou a raiz do CNPJ quando não há grupo. |
| `agente_nome` | Nome legível do agente econômico. Use este nome nas respostas. |
| `acessos` | Acessos do agente no município. |
| `market_share_pct` | Participação do agente nos acessos do município. |
| `posicao` | Posição do agente no município, sendo 1 o líder. |

## `semantic.provedores`

Um CNPJ que declara acessos à Anatel. Para somar um grupo inteiro, use `agente_economico`.

| Coluna | Descrição |
| --- | --- |
| `cnpj` | CNPJ com 14 caracteres, sempre texto, porque pode ser alfanumérico. |
| `provedor` | Nome público do provedor. Empresários individuais não aparecem pelo nome civil. |
| `grupo_economico` | Grupo mais recente declarado à Anatel. `OUTROS` significa sem grupo informado. |
| `agente_economico` | Identificador do grupo, ou a raiz de 8 caracteres do CNPJ quando não há grupo. |
| `agente_nome` | Nome legível do agente econômico. Use este nome nas respostas. |
| `porte_prestadora` | Grande Porte ou Pequeno Porte, conforme a Anatel. |
| `natureza_juridica` | Natureza jurídica na Receita Federal. |
| `capital_social` | Capital social em reais. |
| `uf_sede` | UF da matriz. |
| `data_inicio_atividade` | Data de início de atividade da matriz. |
| `situacao_cadastral` | Nula, Ativa, Suspensa, Inapta ou Baixada. |

## `semantic.snapshot`

Uma linha com a versão dos dados. Use para informar a data de referência.

| Coluna | Descrição |
| --- | --- |
| `snapshot_date` | Primeiro dia do último mês disponível na Anatel. |
| `receita_mes` | Mês de publicação da base do CNPJ, no formato AAAA-MM. |

## `semantic.velocidade_municipal`

Acessos por município, mês e faixa de velocidade.

| Coluna | Descrição |
| --- | --- |
| `mes_referencia` | Primeiro dia do mês. |
| `municipio` | Nome do município. |
| `uf` | Sigla da unidade da federação. |
| `regiao` | Grande região. |
| `municipio_ibge` | Código do IBGE com 7 dígitos. |
| `faixa_velocidade` | Faixa declarada. Quatro das oito faixas só existem em parte da série. |
| `acessos` | Acessos na faixa. |
