-- =====================================================
-- Lumina IQ: Role Management & Google Auth Schema
-- =====================================================

-- =====================================================
-- 1. USER ROLES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS public.user_roles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'handler',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- RLS for user_roles
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

-- Users can read their own role
DROP POLICY IF EXISTS "user_roles_select_own" ON public.user_roles;
CREATE POLICY "user_roles_select_own" ON public.user_roles FOR SELECT USING (auth.uid() = user_id);

-- Only service_role can insert/update/delete (used by backend)
-- No direct client access required for these operations

-- Trigger to keep updated_at current
DO $$
BEGIN
    DROP TRIGGER IF EXISTS update_user_roles_updated_at ON public.user_roles;
    CREATE TRIGGER update_user_roles_updated_at 
        BEFORE UPDATE ON public.user_roles 
        FOR EACH ROW 
        EXECUTE FUNCTION update_updated_at_column();
EXCEPTION
    WHEN undefined_function THEN
        -- Fallback if function doesn't exist
        RAISE NOTICE 'update_updated_at_column() function missing, skipping trigger';
END $$;


-- =====================================================
-- 2. ALLOWED GOOGLE ACCOUNTS TABLE
-- =====================================================
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
