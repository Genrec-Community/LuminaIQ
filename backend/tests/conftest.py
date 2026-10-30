import os
import sys

# Settings are read at import time; give them harmless values (no network is used).
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("INSTITUTION_REQUIRE_APPROVAL", "true")
os.environ.setdefault("INSTITUTION_TRIAL_DAYS", "14")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
