-- Schools at scale: platform approval, subscription timer, school-created student
-- logins and an audit log (services/institution_service.py, services/school_accounts.py,
-- api/v1/endpoints/institutions.py, api/v1/endpoints/platform.py).
-- Additive and safe to run more than once. Backend-only tables (RLS on, no policies).

-- ---------------------------------------------------------------- institutions
-- approval_status: pending (new, waiting for us) | approved | suspended (switched off by us)
-- A school works only while approval_status = 'approved' AND paid_until > now().
ALTER TABLE institutions ADD COLUMN IF NOT EXISTS approval_note   TEXT;
ALTER TABLE institutions ADD COLUMN IF NOT EXISTS approved_at     TIMESTAMPTZ;
ALTER TABLE institutions ADD COLUMN IF NOT EXISTS approved_by     UUID;
ALTER TABLE institutions ADD COLUMN IF NOT EXISTS last_payment_at TIMESTAMPTZ;
ALTER TABLE institutions ADD COLUMN IF NOT EXISTS updated_at      TIMESTAMPTZ NOT NULL DEFAULT now();
-- trial/expired schools may have no paid-up date until they are approved or pay
ALTER TABLE institutions ALTER COLUMN paid_until DROP NOT NULL;

-- Schools that existed before the approval gate keep working (only on the first run,
-- so re-running this file never approves a school that is waiting for review).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'institutions'
                      AND column_name = 'approval_status') THEN
        ALTER TABLE institutions ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'pending';
        UPDATE institutions SET approval_status = 'approved', approved_at = now();
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_institutions_approval ON institutions (approval_status, paid_until);
CREATE INDEX IF NOT EXISTS idx_institutions_paid_until ON institutions (paid_until);
CREATE INDEX IF NOT EXISTS idx_institutions_owner ON institutions (owner_user_id);

-- ------------------------------------------------------------------ members
-- School-created student accounts ("managed"): login_id is studentname-NN@<domain>,
-- only a sign-in name, never a mailbox.
ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS login_id             TEXT;
ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS reg_no               TEXT;
ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS managed              BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS disabled             BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS created_by           UUID;
ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS password_changed_at  TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS uq_institution_members_login_id
    ON institution_members (lower(login_id)) WHERE login_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_institution_members_reg_no
    ON institution_members (institution_id, lower(reg_no)) WHERE reg_no IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_institution_members_inst_role
    ON institution_members (institution_id, role, disabled);

-- --------------------------------------------------------- per-tenant lookups
CREATE INDEX IF NOT EXISTS idx_institution_classes_inst ON institution_classes (institution_id, created_at);
CREATE INDEX IF NOT EXISTS idx_class_members_user ON class_members (user_id);
CREATE INDEX IF NOT EXISTS idx_class_books_class ON class_books (class_id);
CREATE INDEX IF NOT EXISTS idx_class_book_copies_user ON class_book_copies (user_id);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments (razorpay_order_id);
CREATE INDEX IF NOT EXISTS idx_user_plans_institution ON user_plans (institution_id) WHERE institution_id IS NOT NULL;

-- ------------------------------------------------------------------- audit log
-- Who did what to a school: approvals, suspensions, payments, password resets.
CREATE TABLE IF NOT EXISTS institution_audit (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    actor_user_id  UUID,
    action         TEXT NOT NULL,
    detail         JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_institution_audit_inst ON institution_audit (institution_id, created_at DESC);
ALTER TABLE institution_audit ENABLE ROW LEVEL SECURITY;
