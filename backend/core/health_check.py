"""Health Check Service for monitoring system and dependency health."""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional

from qdrant_client import AsyncQdrantClient
from supabase import Client
import httpx

from config.settings import settings
from core.redis_manager import RedisCacheManager

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServiceStatus(str, Enum):
    """Service readiness status enumeration."""
    READY = "ready"
    NOT_READY = "not_ready"


@dataclass
class DependencyStatus:
    """
    Status information for a dependency.
    
    Attributes:
        name: Name of the dependency
        status: Health status (healthy, degraded, unhealthy)
        latency_ms: Response latency in milliseconds
        error_message: Error message if unhealthy (optional)
    """
    name: str
    status: HealthStatus
    latency_ms: float
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
        }
        if self.error_message:
            result["error_message"] = self.error_message
        return result


@dataclass
class HealthCheckResult:
    """
    Result of a health check.
    
    Attributes:
        status: Overall health status
        service: Service name
        version: Service version
        timestamp: ISO timestamp of check
    """
    status: HealthStatus
    service: str
    version: str
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "status": self.status.value,
            "service": self.service,
            "version": self.version,
            "timestamp": self.timestamp,
        }


@dataclass
class ReadinessCheckResult:
    """
    Result of a readiness check.
    
    Attributes:
        status: Overall readiness status
        dependencies: Dictionary of dependency statuses
        cache_status: Cache availability and graceful degradation status
    """
    status: ServiceStatus
    dependencies: Dict[str, DependencyStatus]
    cache_status: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "status": self.status.value,
            "dependencies": {
                name: dep.to_dict() 
                for name, dep in self.dependencies.items()
            },
        }
        
        if self.cache_status:
            result["cache_status"] = self.cache_status
        
        return result


class HealthCheckService:
    """
    Health check service for monitoring system and dependency health.
    
    Provides two types of checks:
    1. Health check: Simple liveness check (is the service running?)
    2. Readiness check: Comprehensive dependency check (can the service handle requests?)
    
    Features:
    - Fast health check (< 100ms)
    - Comprehensive readiness check (< 1 second)
    - Parallel dependency checking
    - Graceful degradation support
    - Detailed error reporting
    """
    
    # Service information
    SERVICE_NAME = "lumina-backend"
    SERVICE_VERSION = "1.0.0"
    
    # Timeout for dependency checks (in seconds)
    DEPENDENCY_TIMEOUT = 5.0
    
    def __init__(
        self,
        redis_manager: RedisCacheManager,
        supabase_client: Client,
        qdrant_client: AsyncQdrantClient,
    ):
        """
        Initialize health check service.
        
        Args:
            redis_manager: Redis cache manager instance
            supabase_client: Supabase database client
            qdrant_client: Qdrant vector database client
        """
        self.redis_manager = redis_manager
        self.supabase_client = supabase_client
        self.qdrant_client = qdrant_client
        
        logger.info("HealthCheckService initialized")
    
    async def check_health(self) -> HealthCheckResult:
        """
        Perform a simple health check.
        
        This is a lightweight check that only verifies the service is running.
        No dependency checks are performed.
        
        Returns:
            HealthCheckResult: Health check result with status and metadata
            
        Response time: < 100ms
        """
        from datetime import datetime
        
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            service=self.SERVICE_NAME,
            version=self.SERVICE_VERSION,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
    
    async def check_readiness(self) -> ReadinessCheckResult:
        """
        Perform a comprehensive readiness check.
        
        Checks all critical dependencies:
        - Redis cache
        - Supabase database
        - Qdrant vector database
        - Azure OpenAI API
        
        Also includes cache status and graceful degradation information.
        
        Returns:
            ReadinessCheckResult: Readiness check result with dependency statuses and cache status
            
        Response time: < 1 second
        Status codes:
            - ready: All dependencies healthy
            - not_ready: One or more dependencies unhealthy
        """
        # Check all dependencies in parallel for speed
        dependency_checks = await asyncio.gather(
            self._check_redis(),
            self._check_supabase(),
            self._check_qdrant(),
            self._check_azure_openai(),
            return_exceptions=True,
        )
        
        # Build dependency status dictionary
        dependencies = {}
        dependency_names = ["redis", "supabase", "qdrant", "azure_openai"]
        
        for name, result in zip(dependency_names, dependency_checks):
            if isinstance(result, Exception):
                # Unexpected exception during check
                dependencies[name] = DependencyStatus(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=0.0,
                    error_message=f"Check failed: {str(result)}",
                )
                logger.error(f"Dependency check for {name} raised exception: {result}")
            else:
                dependencies[name] = result
        
        # Get cache status and graceful degradation information
        cache_status = self._get_cache_status()
        
        # Determine overall readiness status
        # Service is ready only if all dependencies are healthy
        all_healthy = all(
            dep.status == HealthStatus.HEALTHY 
            for dep in dependencies.values()
        )
        
        overall_status = ServiceStatus.READY if all_healthy else ServiceStatus.NOT_READY
        
        # Log readiness status
        if overall_status == ServiceStatus.READY:
            logger.info("Readiness check passed: all dependencies healthy")
        else:
            unhealthy_deps = [
                name for name, dep in dependencies.items() 
                if dep.status != HealthStatus.HEALTHY
            ]
            logger.warning(
                f"Readiness check failed: unhealthy dependencies: {', '.join(unhealthy_deps)}"
            )
        
        return ReadinessCheckResult(
            status=overall_status,
            dependencies=dependencies,
            cache_status=cache_status,
        )
    
    def _get_cache_status(self) -> Dict[str, Any]:
        """
        Get cache status and graceful degradation information.
        
        Returns:
            Dictionary containing:
            - enabled: Whether caching is enabled
            - available: Whether Redis is currently available
            - graceful_degradation: Whether system is operating in degraded mode
            - mode: Current operating mode (normal, degraded)
            - message: Human-readable status message
        """
        is_available = self.redis_manager.is_available
        
        if is_available:
            return {
                "enabled": True,
                "available": True,
                "graceful_degradation": False,
                "mode": "normal",
                "message": "Cache is operational",
            }
        else:
            return {
                "enabled": True,
                "available": False,
                "graceful_degradation": True,
                "mode": "degraded",
                "message": "Cache unavailable - operating in degraded mode without caching. Requests served directly from database.",
            }
    
    async def _check_redis(self) -> DependencyStatus:
        """
        Check Redis cache health.
        
        Returns:
            DependencyStatus: Redis health status
        """
        start_time = time.time()
        
        try:
            # Check if Redis is available
            if not self.redis_manager.is_available:
                return DependencyStatus(
                    name="redis",
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=0.0,
                    error_message="Redis connection not available",
                )
            
            # Perform a simple ping operation
            test_key = "health:check:ping"
            test_value = "pong"
            
            # Set and get to verify read/write operations
            await self.redis_manager.set(test_key, test_value, ttl=10)
            result = await self.redis_manager.get(test_key)
            
            latency_ms = (time.time() - start_time) * 1000
            
            if result == test_value:
                return DependencyStatus(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency_ms,
                )
            else:
                return DependencyStatus(
                    name="redis",
                    status=HealthStatus.DEGRADED,
                    latency_ms=latency_ms,
                    error_message="Redis read/write verification failed",
                )
        
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            return DependencyStatus(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error_message="Redis operation timeout",
            )
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return DependencyStatus(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error_message=f"Redis error: {str(e)}",
            )
    
    async def _check_supabase(self) -> DependencyStatus:
        """
        Check Supabase database health.
        
        Returns:
            DependencyStatus: Supabase health status
        """
        start_time = time.time()
        
        try:
            # Perform a simple query to verify database connectivity
            # Use a lightweight query that doesn't require specific tables
            from concurrent.futures import ThreadPoolExecutor
            import asyncio
            
            loop = asyncio.get_running_loop()
            executor = ThreadPoolExecutor(max_workers=1)
            
            # Run sync Supabase operation in thread pool with timeout
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    lambda: self.supabase_client.table("users").select("id").limit(1).execute()
                ),
                timeout=self.DEPENDENCY_TIMEOUT,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Check if query executed successfully
            if result is not None:
                return DependencyStatus(
                    name="supabase",
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency_ms,
                )
            else:
                return DependencyStatus(
                    name="supabase",
                    status=HealthStatus.DEGRADED,
                    latency_ms=latency_ms,
                    error_message="Supabase query returned None",
                )
        
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            return DependencyStatus(
                name="supabase",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error_message="Supabase query timeout",
            )
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return DependencyStatus(
                name="supabase",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error_message=f"Supabase error: {str(e)}",
            )
    
    async def _check_qdrant(self) -> DependencyStatus:
        """
        Check Qdrant vector database health.
        
        Returns:
            DependencyStatus: Qdrant health status
        """
        start_time = time.time()
        
        try:
            # Get collection list to verify connectivity
            collections = await asyncio.wait_for(
                self.qdrant_client.get_collections(),
                timeout=self.DEPENDENCY_TIMEOUT,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if collections is not None:
                return DependencyStatus(
                    name="qdrant",
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency_ms,
                )
            else:
                return DependencyStatus(
                    name="qdrant",
                    status=HealthStatus.DEGRADED,
                    latency_ms=latency_ms,
                    error_message="Qdrant returned None for collections",
                )
        
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            return DependencyStatus(
                name="qdrant",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error_message="Qdrant operation timeout",
            )
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return DependencyStatus(
                name="qdrant",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error_message=f"Qdrant error: {str(e)}",
            )
    
    async def _check_azure_openai(self) -> DependencyStatus:
        """
        Check Azure OpenAI API health.
        
        Returns:
            DependencyStatus: Azure OpenAI health status
        """
        start_time = time.time()
        
        try:
            # Make a simple API call to verify connectivity
            # Use the deployments endpoint which is lightweight
            url = f"{settings.AZURE_OPENAI_ENDPOINT}/openai/deployments?api-version={settings.AZURE_OPENAI_API_VERSION}"
            
            headers = {
                "api-key": settings.AZURE_OPENAI_API_KEY,
            }
            
            async with httpx.AsyncClient(timeout=self.DEPENDENCY_TIMEOUT) as client:
                response = await client.get(url, headers=headers)
            
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return DependencyStatus(
                    name="azure_openai",
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency_ms,
                )
            else:
                return DependencyStatus(
                    name="azure_openai",
                    status=HealthStatus.DEGRADED,
                    latency_ms=latency_ms,
                    error_message=f"Azure OpenAI returned status {response.status_code}",
                )
        
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            return DependencyStatus(
                name="azure_openai",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error_message="Azure OpenAI API timeout",
            )
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return DependencyStatus(
                name="azure_openai",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error_message=f"Azure OpenAI error: {str(e)}",
            )
    
    async def check_dependency(self, name: str) -> DependencyStatus:
        """
        Check a specific dependency by name.
        
        Args:
            name: Dependency name (redis, supabase, qdrant, azure_openai)
            
        Returns:
            DependencyStatus: Status of the specified dependency
            
        Raises:
            ValueError: If dependency name is not recognized
        """
        dependency_checks = {
            "redis": self._check_redis,
            "supabase": self._check_supabase,
            "qdrant": self._check_qdrant,
            "azure_openai": self._check_azure_openai,
        }
        
        if name not in dependency_checks:
            raise ValueError(
                f"Unknown dependency: {name}. "
                f"Valid options: {', '.join(dependency_checks.keys())}"
            )
        
        check_func = dependency_checks[name]
        return await check_func()
