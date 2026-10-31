-- =============================================================================
-- Runs in SUPABASE (not the app database). Supabase keeps the user accounts, so
-- the rule "only allow-listed Google accounts may sign up" must live next to
-- auth.users. Everything else is in db/schema/ on our own Postgres.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.allowed_google_accounts (
    email VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    added_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

-- RLS for allowed_google_accounts
ALTER TABLE public.allowed_google_accounts ENABLE ROW LEVEL SECURITY;
-- Service role bypasses RLS. We can allow admins to read this if needed later.


-- =====================================================
-- 3. GOOGLE SIGNUP RESTRICTION TRIGGER
-- =====================================================
-- This function runs BEFORE an insert into auth.users.
-- It checks if the user is signing up via Google. If so, it verifies their email is allowed.
CREATE OR REPLACE FUNCTION public.check_allowed_google_account()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if the provider is google. raw_app_meta_data contains {"provider": "google", "providers": ["google"]}
    IF NEW.raw_app_meta_data->>'provider' = 'google' THEN
        IF NOT EXISTS (SELECT 1 FROM public.allowed_google_accounts WHERE email = NEW.email) THEN
            RAISE EXCEPTION 'This Google account (%) is not authorized to access the system.', NEW.email;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop trigger if exists and recreate
DROP TRIGGER IF EXISTS enforce_allowed_google_accounts ON auth.users;
CREATE TRIGGER enforce_allowed_google_accounts
    BEFORE INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.check_allowed_google_account();
