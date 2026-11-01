-- Roda uma vez, quando o volume do Postgres é criado.
CREATE EXTENSION IF NOT EXISTS vector;

-- Langfuse guarda os metadados dele em um banco separado do warehouse.
-- Sem CONNECT público, os usuários do agente nunca alcançam esse banco.
CREATE DATABASE langfuse;
REVOKE CONNECT ON DATABASE langfuse FROM PUBLIC;
