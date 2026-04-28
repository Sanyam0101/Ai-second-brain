-- note_links: explicit user-defined connections between notes (replaces Neo4j graph edges)
CREATE TABLE IF NOT EXISTS note_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  src_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
  dst_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(src_id, dst_id)
);
