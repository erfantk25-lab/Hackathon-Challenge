-- Enable pgvector extension for storing embeddings.
-- This script runs automatically the first time the postgres
-- volume is created. To re-run it, delete the volume:
--   docker compose down -v
CREATE EXTENSION IF NOT EXISTS vector;