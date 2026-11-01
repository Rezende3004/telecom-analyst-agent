# ADR-003: Dados pessoais em uma demo pública

**Status:** aceito · **Data:** 2026-10-31

## Contexto

Os arquivos abertos da Receita Federal são públicos, mas isso não torna qualquer uso adequado sob a LGPD. O plano já proibia nomes de sócios na demo. Ao inspecionar os arquivos, surgiram riscos que ele não previa:

- A razão social de MEIs traz o nome civil seguido do **CPF completo**.
- `Estabelecimentos` traz endereço, telefone e e-mail, muitas vezes pessoais em empresas pequenas.
- O nome da prestadora na Anatel pode ser o nome civil de um empresário individual.

## Decisão

Aplicar minimização antes de os dados chegarem ao warehouse:

- **Recorte:** só empresas de telecom ou declarantes da Anatel entram no staging.
- **Remoção de CPF:** sequências de 11 dígitos saem da razão social e do nome fantasia. Um contrato pandera falha se alguma sobrar.
- **Campos descartados:** endereço, CEP, telefone, e-mail, nome do representante legal e faixa etária nunca saem dos arquivos brutos.
- **Nome público:** empresários individuais (natureza 2135) aparecem pelo nome fantasia ou como `Empresário individual` mais a raiz do CNPJ.
- **Nomes da Anatel:** o CPF também aparece nos nomes declarados à Anatel, então a remoção vale ali. Um nome fantasia igual à razão social de um empresário individual é tratado como nome civil.
- **Busca de provedores:** nenhum nome igual à razão social de um empresário individual entra em `nomes_provedores`, mesmo vindo de outro CNPJ.
- **Sócios:** a tabela fica no staging local e não é carregada no Postgres. O agente nunca a enxerga.
- **Testes:** `semantic_sem_cpf`, `nomes_sem_cpf` e `nomes_sem_empresario_individual` falham se um nome exposto tiver formato de CPF ou repetir um nome civil. Eles já barraram 13 nomes com CPF e 11 nomes civis ao trazer os nomes da Anatel para o warehouse.

## Consequências

- Os dados brutos em `data/raw/` continuam com esses campos. Eles ficam fora do git e não vão para a VPS.
- O nome fantasia de um empresário individual ainda pode conter um nome civil. A regra reduz esse risco, mas não o elimina.
- O grafo da Fase 2 vai precisar dos sócios e terá de publicar apenas agregados por grupo.
