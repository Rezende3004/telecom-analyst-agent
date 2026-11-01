# ADR-006: Evals no CI sem LLM e com snapshot reduzido

**Status:** aceito, com a publicação do snapshot pendente · **Data:** 2026-11-01

## Contexto

O plano pede evals em todo PR que altere o agente ou os prompts, sobre um snapshot congelado. Duas medições mudaram o caminho:

- **O snapshot completo tem 397 MB** e traz tudo, incluindo tabelas que nenhuma pergunta usa.
- **O modelo local é lento sem GPU.** Com 4 threads, um passo levou 96 s. As 142 perguntas, com cerca de 2,5 passos cada, levariam perto de 10 horas por PR, e os runners do GitHub são mais fracos que a máquina medida.

## Decisão

**Snapshot reduzido.** `evals/snapshot.py` exporta só o que as perguntas usam: toda a série de `mercado_municipal` e os meses citados nas tabelas grandes. A view `provedores` fica de fora, porque traz capital social e nenhuma pergunta precisa dela. O exportador recusa gerar o arquivo se um nome tiver formato de CPF.

| Medida | Completo | Reduzido |
| --- | --- | --- |
| Tamanho | 397 MB | 40,9 MB |
| Linhas de `acessos_mensais` | 16,1 milhões | 402 mil |
| Referências com resultado equivalente | 138 de 138 | 138 de 138 |

**CI determinístico.** `evals.yml` roda em PRs do agente e confere, sem LLM, as 138 SQLs de referência, os guardrails e 21 buscas de provedor.

**Modelo só sob demanda.** Uma amostra com o modelo local em CPU existe como execução manual. A suíte completa continua local, com `make evals`, e os relatórios ficam em `docs/eval-reports/`.

**Publicação depois de revisão.** O workflow só roda quando a variável `EVAL_SNAPSHOT_TAG` existe, o que acontece depois de o pacote ser aprovado e publicado como Release.

## Consequências

- **Um PR pode piorar o agente sem o CI perceber.** O CI protege dados, guardrails e busca, mas não a qualidade das respostas do LLM. Rodar `make evals` antes de mudar prompts continua sendo disciplina manual.
- **Um modelo via API mudaria isso.** Com uma chave, a suíte completa caberia no CI, a um custo por execução.
- **O snapshot publicado contém nomes reais de provedores.** São dados públicos da Anatel. Remover um provedor quebraria totais e market shares.
- **O caminho de restauração só foi testado localmente** até a primeira publicação.
