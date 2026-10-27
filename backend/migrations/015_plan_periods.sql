-- Exact plan periods for personal plans (services/billing_service.py).
-- Additive only; safe to run more than once.

-- When the current paid period started and when the last payment landed
ALTER TABLE user_plans ADD COLUMN IF NOT EXISTS current_period_start TIMESTAMPTZ;
ALTER TABLE user_plans ADD COLUMN IF NOT EXISTS last_payment_at TIMESTAMPTZ;

-- The exact term each payment bought (one row per Razorpay payment)
ALTER TABLE payments ADD COLUMN IF NOT EXISTS period_start TIMESTAMPTZ;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS period_end TIMESTAMPTZ;

-- Checkout lookups (verify and webhook find the order or subscription they belong to)
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments (razorpay_order_id) WHERE razorpay_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_payments_subscription ON payments (razorpay_subscription_id) WHERE razorpay_subscription_id IS NOT NULL;
-- Plans that end soon (reminders, reports)
CREATE INDEX IF NOT EXISTS idx_user_plans_period_end ON user_plans (current_period_end) WHERE source = 'razorpay';
