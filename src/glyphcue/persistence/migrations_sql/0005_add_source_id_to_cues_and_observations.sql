ALTER TABLE cues ADD COLUMN source_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_cues_source_id ON cues(source_id);

ALTER TABLE observations ADD COLUMN source_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_observations_source_id ON observations(source_id);