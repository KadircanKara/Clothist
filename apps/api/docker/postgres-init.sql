-- Extensions enabled on first container init.
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector, used for embeddings later
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- trigram similarity for fuzzy search
