-- Lena Virtual Assistant — Supabase Tables
-- Run in Supabase SQL Editor: Dashboard → SQL Editor → New Query

-- 1. Conversations (chat history)
CREATE TABLE conversations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_conversations_user ON conversations (user_id, created_at);

-- 2. Facts (long-term memory)
CREATE TABLE facts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL,
    category text NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    created_at timestamptz DEFAULT now(),
    UNIQUE (user_id, category, key)
);
CREATE INDEX idx_facts_user ON facts (user_id);

-- 3. Todos
CREATE TABLE todos (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL,
    title text NOT NULL,
    priority text DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    status text DEFAULT 'open' CHECK (status IN ('open', 'done')),
    due_date timestamptz,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_todos_user_status ON todos (user_id, status);

-- 4. Reminders
CREATE TABLE reminders (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL,
    text text NOT NULL,
    remind_at timestamptz NOT NULL,
    recurring text,
    sent boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_reminders_pending ON reminders (sent, remind_at) WHERE sent = false;

-- 5. Knowledge (Lena-specific knowledge base)
CREATE TABLE knowledge (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL,
    category text NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    created_at timestamptz DEFAULT now(),
    UNIQUE (user_id, category, key)
);
CREATE INDEX idx_knowledge_user ON knowledge (user_id);

-- 6. Audit Log
CREATE TABLE audit_log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL,
    action text NOT NULL,
    details jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_audit_user ON audit_log (user_id, created_at);
