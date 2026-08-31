CREATE TABLE observations (
    id TEXT PRIMARY KEY,
    evidence_run_id TEXT NOT NULL,
    text TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    language TEXT,
    confidence REAL,
    roi_x REAL,
    roi_y REAL,
    roi_width REAL,
    roi_height REAL,
    geometry TEXT,
    frame_reference TEXT,
    provenance_kind TEXT NOT NULL,
    provenance_source TEXT NOT NULL,
    provenance_detail TEXT NOT NULL DEFAULT ''
);

CREATE INDEX idx_observations_evidence_run_id ON observations(evidence_run_id);
