-- Institution plan (services/institution_service.py, api/v1/endpoints/institutions.py).
-- Additive only; backend-only tables (RLS on, no policies).

CREATE TABLE IF NOT EXISTS institutions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name           TEXT NOT NULL,
    owner_user_id  UUID NOT NULL,
    contact_email  TEXT,
    billing_name   TEXT,
    gstin          TEXT,
    seats          INTEGER NOT NULL DEFAULT 25,          -- student seats
    status         TEXT NOT NULL DEFAULT 'trial',        -- trial | active | expired
    paid_until     TIMESTAMPTZ,                          -- trial end or paid-up date
    teacher_code   TEXT NOT NULL UNIQUE,                 -- teachers join with this
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS institution_members (
    institution_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    user_id        UUID NOT NULL,
    role           TEXT NOT NULL,                        -- admin | teacher | student
    display_name   TEXT,
    email          TEXT,
    joined_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (institution_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_institution_members_user ON institution_members (user_id);

CREATE TABLE IF NOT EXISTS institution_classes (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    invite_code    TEXT NOT NULL UNIQUE,                 -- students join with this
    created_by     UUID,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Students in a class and the project their class books are copied into
CREATE TABLE IF NOT EXISTS class_members (
    class_id   UUID NOT NULL REFERENCES institution_classes(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    joined_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (class_id, user_id)
);

-- Books a teacher published to a class
CREATE TABLE IF NOT EXISTS class_books (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id           UUID NOT NULL REFERENCES institution_classes(id) ON DELETE CASCADE,
    source_document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title              TEXT,
    published_by       UUID,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (class_id, source_document_id)
);

-- Each student's copy of a class book
CREATE TABLE IF NOT EXISTS class_book_copies (
    class_book_id UUID NOT NULL REFERENCES class_books(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL,
    document_id   UUID REFERENCES documents(id) ON DELETE CASCADE,
    PRIMARY KEY (class_book_id, user_id)
);

ALTER TABLE institutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE institution_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE institution_classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_books ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_book_copies ENABLE ROW LEVEL SECURITY;
