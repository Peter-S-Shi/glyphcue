CREATE TABLE track_groups (
    id TEXT PRIMARY KEY,
    roi_x REAL NOT NULL,
    roi_y REAL NOT NULL,
    roi_width REAL NOT NULL,
    roi_height REAL NOT NULL,
    languages TEXT NOT NULL
);
