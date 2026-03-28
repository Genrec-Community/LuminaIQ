"""Pytest configuration and shared fixtures."""

import pytest
import asyncio
import sys
import os
from typing import Generator

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
