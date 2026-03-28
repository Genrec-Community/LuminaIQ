# LuminaIQ Backend Tests

This directory contains the test suite for the LuminaIQ backend application.

## Directory Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Shared pytest fixtures and configuration
├── unit/                    # Unit tests (fast, no external dependencies)
│   ├── __init__.py
│   └── test_redis_manager.py
└── integration/             # Integration tests (require external services)
    ├── __init__.py
    ├── test_redis_integration.py
    ├── test_cache_warming.py
    └── test_signed_url.py
```

## Running Tests

### Run all tests
```bash
cd backend
python -m pytest
```

### Run only unit tests
```bash
python -m pytest -m unit
```

### Run only integration tests
```bash
python -m pytest -m integration
```

### Run specific test file
```bash
python -m pytest tests/unit/test_redis_manager.py
```

### Run with verbose output
```bash
python -m pytest -v
```

### Run with coverage report
```bash
python -m pytest --cov=backend --cov-report=html
```

## Test Categories

### Unit Tests (`-m unit`)
- Fast execution (< 1 second per test)
- No external dependencies (Redis, Supabase, etc.)
- Test individual components in isolation
- Use mocks for external dependencies

### Integration Tests (`-m integration`)
- Require external services (Redis, Supabase, Qdrant)
- Test component interactions
- May be slower (seconds to minutes)
- Verify end-to-end functionality

## Writing Tests

### Unit Test Example
```python
import pytest
from core.redis_manager import RedisCacheManager

@pytest.mark.unit
def test_redis_manager_initialization():
    manager = RedisCacheManager(host="localhost", port=6379)
    assert manager.host == "localhost"
```

### Integration Test Example
```python
import pytest
from core.redis_manager import RedisCacheManager

@pytest.mark.asyncio
@pytest.mark.integration
async def test_redis_connection():
    manager = RedisCacheManager(host="localhost", port=6379)
    await manager.connect()
    assert manager.is_available
    await manager.disconnect()
```

## Test Fixtures

Common fixtures are defined in `conftest.py`:

- `event_loop`: Async event loop for async tests
- `redis_config`: Redis configuration dictionary
- `redis_manager`: Pre-configured RedisCacheManager instance

## Requirements

Install test dependencies:
```bash
pip install pytest pytest-asyncio
```

For integration tests, ensure external services are running:
- Redis (localhost:6379)
- Supabase (configured in .env)
- Qdrant (configured in .env)

## CI/CD Integration

Tests can be run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run unit tests
  run: python -m pytest -m unit

- name: Run integration tests
  run: python -m pytest -m integration
  env:
    REDIS_HOST: localhost
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
```

## Best Practices

1. **Keep unit tests fast** - Mock external dependencies
2. **Mark tests appropriately** - Use `@pytest.mark.unit` or `@pytest.mark.integration`
3. **Clean up resources** - Use fixtures with proper teardown
4. **Use descriptive names** - Test names should describe what they test
5. **One assertion per test** - Keep tests focused and simple
6. **Test edge cases** - Include error conditions and boundary values

## Troubleshooting

### Redis connection errors
Ensure Redis is running:
```bash
redis-cli ping
# Should return: PONG
```

### Import errors
Make sure you're running tests from the backend directory:
```bash
cd backend
python -m pytest
```

### Async test errors
Ensure pytest-asyncio is installed:
```bash
pip install pytest-asyncio
```
