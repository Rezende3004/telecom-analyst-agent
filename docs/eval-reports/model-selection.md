# Seleção de modelo: comparação parcial

Modelos Claude acertam de 92% a 100% das perguntas novas, enquanto o modelo local de 4B acerta 54%. A diferença mostra espaço para fine-tuning. A seleção ainda não está concluída: faltam latência, custo e chamadas reais de ferramenta.

| Modelo | Perguntas novas, às cegas |
| --- | --- |
| `qwen3.5:4b`, local | 54% (21 de 39) |
| Claude Haiku 5.5 | 92% (36 de 39) |
| Claude Sonnet 5.5 | 100% (39 de 39) |

Detalhes por categoria no [relatório v2](v2.md). A primeira comparação, nas 103 perguntas originais, está abaixo.

## Primeira comparação: 103 perguntas originais

| Modelo | Teste | Desenvolvimento | Total | SQL com erro |
| --- | --- | --- | --- | --- |
| `qwen3.5:4b`, local | 60% (30 de 50) | 91% (48 de 53) | 76% | 11 de 62 chamadas no teste |
| Claude Haiku 5.5 | 100% (50 de 50) | 100% (53 de 53) | 100% | 0 de 103 |
| Claude Sonnet 5.5 | 96% (48 de 50) | 100% (53 de 53) | 98% | 0 de 103 |

Critérios do plano ainda não medidos:

| Critério | Situação |
| --- | --- |
| Execution accuracy | medida |
| Chamadas de ferramenta malformadas | não medida: os modelos Claude só devolveram SQL |
| Latência p95 | não medida: rodaram em lote |
| Custo por 1.000 perguntas | não medido |

## Como foi medido

Os modelos Claude rodaram como agentes novos de uma sessão do Claude Code, sem chave de API. Cada um recebeu o mesmo prompt congelado e o mesmo esquema do agente local, mais as 103 perguntas embaralhadas, sem as SQLs de referência. As respostas passaram pelos mesmos guardrails, pelo mesmo usuário somente leitura e pelo mesmo comparador. O registro de ferramentas confirma que nenhum dos dois leu o golden set nem consultou o banco.

## Como ler estes números

- **As condições são diferentes.** O modelo local respondeu uma pergunta por vez, com ferramentas, execução da SQL e chance de corrigir erros. Os modelos Claude viram todas as perguntas juntas e escreveram tudo sem executar nada. A falta de retentativas os desfavorece, e ver perguntas parecidas juntas pode favorecê-los.
- **Haiku não ficou provado melhor que Sonnet.** A única diferença são as 2 perguntas ambíguas sobre Palmas, em que o Haiku assumiu Tocantins, a mesma cidade da referência, e o Sonnet devolveu as duas cidades.
- **O conjunto original saturou.** Com 100%, ele não distinguia os modelos grandes. As 39 perguntas novas distinguem: Sonnet ficou acima de Haiku por 3 perguntas, ainda poucas para uma conclusão firme.
- **É uma rodada só.** Não há repetições nem medida de variação.
- **Isto não é um caminho de produção.** Uma sessão do Claude Code serviu para medir. O produto depende de um modelo local ou de uma API.

## A comparação corrigiu o golden set

Haiku e Sonnet discordaram da referência nas 3 perguntas "quantos provedores perderam acessos". A referência estava errada: ignorava quem zerou a base na cidade, e em Sobral dava 9 em vez de 18. Ela foi corrigida, e as notas acima já usam a versão nova. A nota do modelo local não mudou, porque ele errava esses casos de qualquer forma.

## Decisão

- **O modelo padrão continua local.** O projeto funciona sem API e sem custo por pergunta, e a Fase 3 existe para reduzir essa diferença.
- **Haiku e Sonnet seguem candidatos ao papel de modelo grande.** Sonnet acertou mais nas perguntas novas, por uma margem pequena. O custo vai decidir se essa margem compensa.
- **A seleção final exige chamadas reais de API**, com o loop completo, medindo ferramentas, latência e custo.
