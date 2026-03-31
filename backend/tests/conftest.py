"""Pytest configuration and shared fixtures."""

import pytest
import asyncio
import sys
import os
from typing import Generator

# ---------------------------------------------------------------------------
# Environment bootstrap
# Must happen BEFORE any project module is imported, because config/settings.py
# instantiates Settings() at module level and requires these variables.
#
# Why needed:
#   - The .env file has stale LLM_* keys that Settings now forbids as "extra".
#   - The .env is missing AZURE_OPENAI_* keys that Settings now requires.
# These stubs allow Settings to load; unit tests mock the actual services.
# ---------------------------------------------------------------------------
_STUB_ENV = {
    # Required fields missing from local .env
    "AZURE_OPENAI_API_KEY": "stub-azure-key-for-tests",
    "AZURE_OPENAI_ENDPOINT": "https://stub.openai.azure.com/",
    "AZURE_OPENAI_DEPLOYMENT": "stub-deployment",
    # Extra keys in .env that Settings now forbids — remove them so pydantic
    # doesn't raise "Extra inputs are not permitted".
}
for _k, _v in _STUB_ENV.items():
    os.environ.setdefault(_k, _v)

# Remove stale keys that are no longer in the Settings model
for _stale_key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
    os.environ.pop(_stale_key, None)

# Add parent directory to Python path so 'backend' module can be imported
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def redis_config():
    """Redis configuration for testing."""
    return {
        "host": "localhost",
        "port": 6379,
        "password": "",
        "db": 0,
        "max_connections": 50,
    }


@pytest.fixture
async def redis_manager(redis_config):
    """Create a RedisCacheManager instance for testing."""
    from core.redis_manager import RedisCacheManager
    
    manager = RedisCacheManager(**redis_config)
    await manager.connect()
    
    yield manager
    
    # Cleanup
    await manager.disconnect()
