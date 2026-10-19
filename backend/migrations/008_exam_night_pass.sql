-- Exam Night Pass: 48h of Topper on top of whatever plan the user has
-- (services/billing_service.py grant_pass, services/usage_service.py plan_row).
ALTER TABLE user_plans ADD COLUMN IF NOT EXISTS pass_until TIMESTAMPTZ;
