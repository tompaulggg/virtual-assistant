-- Susi — additional tables for project tracking and ideas

-- 1. Projects (track status of all Thomas' projects)
CREATE TABLE projects (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL,
    project text NOT NULL,
    status text NOT NULL DEFAULT 'aktiv',
    notes text DEFAULT '',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE (user_id, project)
);
CREATE INDEX idx_projects_user ON projects (user_id);

-- 2. Ideas (capture and prioritize ideas)
CREATE TABLE ideas (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL,
    idea text NOT NULL,
    project text DEFAULT 'allgemein',
    status text DEFAULT 'neu' CHECK (status IN ('neu', 'priorisiert', 'erledigt', 'verworfen')),
    created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_ideas_user_status ON ideas (user_id, status);
