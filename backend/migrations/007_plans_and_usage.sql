-- Plans, usage metering and payments (services/plans.py, services/usage_service.py,
-- api/v1/endpoints/billing.py). Additive only. Backend-only tables (RLS on, no policies).

-- Current plan per user. No row = Free.
CREATE TABLE IF NOT EXISTS user_plans (
    user_id                  UUID PRIMARY KEY,
    plan                     TEXT NOT NULL DEFAULT 'free',     -- free | scholar | topper | institution
    status                   TEXT NOT NULL DEFAULT 'active',   -- active | authenticated | pending | halted | cancelled | expired
    source                   TEXT NOT NULL DEFAULT 'manual',   -- razorpay | pass | institution | manual
    billing_cycle            TEXT,                              -- monthly | yearly
    current_period_end       TIMESTAMPTZ,                       -- NULL = no expiry
    cancel_at_period_end     BOOLEAN NOT NULL DEFAULT false,
    razorpay_subscription_id TEXT UNIQUE,
    razorpay_customer_id     TEXT,
    institution_id           UUID,
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Usage per user, feature and period ('d:2026-10-19', 'm:2026-10' or 't')
CREATE TABLE IF NOT EXISTS usage_counters (
    user_id     UUID NOT NULL,
    feature     TEXT NOT NULL,
    period      TEXT NOT NULL,
    count       INTEGER NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, feature, period)
);

-- LLM tokens per user, day, model and feature (real cost measurement)
CREATE TABLE IF NOT EXISTS llm_usage_daily (
    user_id        UUID,
    day            DATE NOT NULL,
    model          TEXT NOT NULL,
    feature        TEXT NOT NULL,
    calls          INTEGER NOT NULL DEFAULT 0,
    input_tokens   BIGINT NOT NULL DEFAULT 0,
    output_tokens  BIGINT NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_usage_daily_key
    ON llm_usage_daily (COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid), day, model, feature);

-- Every payment / subscription event we've seen (audit trail, idempotency)
CREATE TABLE IF NOT EXISTS payments (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  UUID,
    kind                     TEXT NOT NULL,            -- subscription | pass | seats
    plan                     TEXT,
    amount_paise             INTEGER,
    currency                 TEXT DEFAULT 'INR',
    status                   TEXT NOT NULL,            -- created | paid | failed | refunded
    razorpay_order_id        TEXT,
    razorpay_payment_id      TEXT UNIQUE,
    razorpay_subscription_id TEXT,
    raw                      JSONB,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_payments_user ON payments (user_id, created_at DESC);

-- Webhook events already processed (Razorpay retries deliveries)
CREATE TABLE IF NOT EXISTS billing_events (
    event_id    TEXT PRIMARY KEY,
    event       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE user_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_counters ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_usage_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_events ENABLE ROW LEVEL SECURITY;

-- Atomically add p_amount if it stays within p_limit (-1 = no limit).
-- Returns the new count, or -1 when the limit would be exceeded.
CREATE OR REPLACE FUNCTION consume_usage(p_user UUID, p_feature TEXT, p_period TEXT, p_amount INTEGER, p_limit INTEGER)
RETURNS INTEGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v INTEGER;
BEGIN
    INSERT INTO usage_counters (user_id, feature, period, count)
    VALUES (p_user, p_feature, p_period, 0)
    ON CONFLICT (user_id, feature, period) DO NOTHING;

    UPDATE usage_counters
       SET count = count + p_amount, updated_at = now()
     WHERE user_id = p_user AND feature = p_feature AND period = p_period
       AND (p_limit < 0 OR count + p_amount <= p_limit)
    RETURNING count INTO v;

    RETURN COALESCE(v, -1);
END $$;

CREATE OR REPLACE FUNCTION add_llm_usage(p_user UUID, p_day DATE, p_model TEXT, p_feature TEXT, p_input BIGINT, p_output BIGINT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO llm_usage_daily (user_id, day, model, feature, calls, input_tokens, output_tokens)
    VALUES (p_user, p_day, p_model, p_feature, 1, p_input, p_output)
    ON CONFLICT (COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid), day, model, feature)
    DO UPDATE SET calls = llm_usage_daily.calls + 1,
                  input_tokens = llm_usage_daily.input_tokens + EXCLUDED.input_tokens,
                  output_tokens = llm_usage_daily.output_tokens + EXCLUDED.output_tokens;
END $$;

-- Only the backend (service role) may call these
REVOKE ALL ON FUNCTION consume_usage(UUID, TEXT, TEXT, INTEGER, INTEGER) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION add_llm_usage(UUID, DATE, TEXT, TEXT, BIGINT, BIGINT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION consume_usage(UUID, TEXT, TEXT, INTEGER, INTEGER) TO service_role;
GRANT EXECUTE ON FUNCTION add_llm_usage(UUID, DATE, TEXT, TEXT, BIGINT, BIGINT) TO service_role;
