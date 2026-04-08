-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column (nullable for backward compat)
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS embedding vector(512);

-- Add updated_at for tracking changes
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- RPC function for semantic similarity search
CREATE OR REPLACE FUNCTION match_knowledge(
    query_embedding vector(512),
    match_user_id text,
    match_threshold float DEFAULT 0.3,
    match_count int DEFAULT 12
)
RETURNS TABLE (
    id bigint,
    category text,
    key text,
    value text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        k.id,
        k.category,
        k.key,
        k.value,
        1 - (k.embedding <=> query_embedding) AS similarity
    FROM knowledge k
    WHERE k.user_id = match_user_id
      AND k.embedding IS NOT NULL
      AND 1 - (k.embedding <=> query_embedding) > match_threshold
    ORDER BY k.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Note: Run AFTER backfill_embeddings.py has populated embeddings:
-- CREATE INDEX idx_knowledge_embedding ON knowledge
--   USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
