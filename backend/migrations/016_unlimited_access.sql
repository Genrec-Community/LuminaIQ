-- ============================================================
-- Unlimited access for testers and staff
-- ============================================================
-- Emails on this list skip every plan limit, whatever their plan (their
-- user_plans row, school membership and billing are untouched). Works for
-- people who haven't signed up yet: the match is by email at check time.
--
-- Add someone:    INSERT INTO unlimited_access (email, note) VALUES ('x@gmail.com', 'tester');
-- Remove someone: DELETE FROM unlimited_access WHERE email = 'x@gmail.com';
-- ============================================================

CREATE TABLE IF NOT EXISTS unlimited_access (
    email    TEXT PRIMARY KEY CHECK (email = lower(email)),
    note     TEXT,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE unlimited_access ENABLE ROW LEVEL SECURITY;  -- service role only

-- auth.users isn't reachable through the API, so the backend asks this function
CREATE OR REPLACE FUNCTION is_unlimited(p_user UUID)
RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, auth
AS $$
    SELECT EXISTS (
        SELECT 1 FROM auth.users u
        JOIN public.unlimited_access a ON a.email = lower(u.email)
        WHERE u.id = p_user
    );
$$;
REVOKE ALL ON FUNCTION is_unlimited(UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION is_unlimited(UUID) TO service_role;
