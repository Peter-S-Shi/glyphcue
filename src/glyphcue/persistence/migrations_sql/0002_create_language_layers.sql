CREATE TABLE language_layers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cue_id TEXT NOT NULL REFERENCES cues(id),
    position INTEGER NOT NULL,
    language TEXT NOT NULL,
    text TEXT NOT NULL,
    observation_ids TEXT NOT NULL DEFAULT ''
);
