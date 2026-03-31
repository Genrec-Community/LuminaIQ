"""
Telemetry service for Azure Application Insights integration using OpenTelemetry.

This module provides comprehensive observability through Azure Application Insights,
including request telemetry, exception tracking, dependency monitoring, custom metrics,
and distributed tracing using the vendor-neutral OpenTelemetry standard.
"""

import os
import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import Sampler, SamplingResult, ParentBased, ALWAYS_ON, TraceIdRatioBased, Decision
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.trace import Status, StatusCode, SpanKind
from opentelemetry.semconv.trace import SpanAttributes

try:
    from azure.monitor.opentelemetry.exporter import (
        AzureMonitorTraceExporter,
        AzureMonitorMetricExporter,
        AzureMonitorLogExporter
    )
    AZURE_MONITOR_AVAILABLE = True
except ImportError:
    AZURE_MONITOR_AVAILABLE = False


logger = logging.getLogger(__name__)


class TelemetryService:
    """
    Service for tracking telemetry data to Azure Application Insights using OpenTelemetry.
    
    Provides methods for:
    - Request telemetry (duration, status code, endpoint)
    - Exception telemetry (stack traces, context)
    - Dependency telemetry (Redis, Supabase, Qdrant, LLM API)
    - Custom metrics (cache hit rate, job queue length, etc.)
    - Distributed tracing with OpenTelemetry
    
    OpenTelemetry is vendor-neutral and can export to multiple backends.
    """
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        service_name: str = "lumina-backend",
        service_version: str = "1.0.0"
    ):
        """
        Initialize the telemetry service.
        
        Args:
            connection_string: Azure Application Insights connection string
            service_name: Name of the service for telemetry
            service_version: Version of the service
        
        Note:
            If connection string is not provided, telemetry will be disabled.
        """
        self.connection_string = connection_string or os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        self.service_name = service_name
        self.service_version = service_version
        self.enabled = bool(self.connection_string and AZURE_MONITOR_AVAILABLE)
        
        if not AZURE_MONITOR_AVAILABLE:
            logger.warning(
                "Azure Monitor OpenTelemetry exporter not available. "
                "Install azure-monitor-opentelemetry-exporter to enable telemetry."
            )
            return
        
        if not self.enabled:
            logger.warning(
                "Application Insights not configured. "
                "Set APPLICATIONINSIGHTS_CONNECTION_STRING to enable telemetry."
            )
            return
        
        # Create resource with service information
        self.resource = Resource.create({
            SERVICE_NAME: self.service_name,
            SERVICE_VERSION: self.service_version,
        })
        
        # Initialize tracing
        self._setup_tracing()
        
        # Initialize metrics
        self._setup_metrics()
        
        logger.info(f"OpenTelemetry telemetry initialized for {self.service_name} v{self.service_version}")

    def _setup_tracing(self) -> None:
        """Set up distributed tracing with Azure Monitor."""
        try:
            # Create Azure Monitor trace exporter
            trace_exporter = AzureMonitorTraceExporter(
                connection_string=self.connection_string
            )
            
            # Create tracer provider with adaptive sampling
            tracer_provider = TracerProvider(
                resource=self.resource,
                sampler=AdaptiveSampler()
            )
            
            # Add span processor
            span_processor = BatchSpanProcessor(trace_exporter)
            tracer_provider.add_span_processor(span_processor)
            
            # Set global tracer provider
            trace.set_tracer_provider(tracer_provider)
            
            # Get tracer
            self.tracer = trace.get_tracer(
                instrumenting_module_name=__name__,
                instrumenting_library_version=self.service_version
            )
            
            logger.info("Tracing initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize tracing: {e}")
            self.tracer = None
    
    def _setup_metrics(self) -> None:
        """Set up metrics collection with Azure Monitor."""
        try:
            # Create Azure Monitor metric exporter
            metric_exporter = AzureMonitorMetricExporter(
                connection_string=self.connection_string
            )
            
            # Create metric reader with 60-second export interval
            metric_reader = PeriodicExportingMetricReader(
                exporter=metric_exporter,
                export_interval_millis=60000  # 60 seconds
            )
            
            # Create meter provider
            meter_provider = MeterProvider(
                resource=self.resource,
                metric_readers=[metric_reader]
            )
            
            # Set global meter provider
            metrics.set_meter_provider(meter_provider)
            
            # Get meter
            self.meter = metrics.get_meter(
                name=__name__,
                version=self.service_version
            )
            
            # Create common metrics
            self._create_metrics()
            
            logger.info("Metrics initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize metrics: {e}")
            self.meter = None
    
    def _create_metrics(self) -> None:
        """Create common metric instruments."""
        if not self.meter:
            return
        
        # Request metrics
        self.request_duration = self.meter.create_histogram(
            name="http.server.request.duration",
            description="HTTP request duration in milliseconds",
            unit="ms"
        )
        
        self.request_counter = self.meter.create_counter(
            name="http.server.request.count",
            description="Total number of HTTP requests",
            unit="1"
        )
        
        # Cache metrics
        self.cache_hit_counter = self.meter.create_counter(
            name="cache.hit",
            description="Number of cache hits",
            unit="1"
        )
        
        self.cache_miss_counter = self.meter.create_counter(
            name="cache.miss",
            description="Number of cache misses",
            unit="1"
        )
        
        # Job metrics
        self.job_queue_length = self.meter.create_up_down_counter(
            name="job.queue.length",
            description="Number of jobs in queue",
            unit="1"
        )
        
        self.job_duration = self.meter.create_histogram(
            name="job.duration",
            description="Job processing duration in milliseconds",
            unit="ms"
        )
        
        # Dependency metrics
        self.dependency_duration = self.meter.create_histogram(
            name="dependency.duration",
            description="Dependency call duration in milliseconds",
            unit="ms"
        )

    def track_request(
        self,
        name: str,
        duration: float,
        status_code: int,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track an HTTP request.
        
        Args:
            name: Request name (e.g., "GET /api/v1/documents")
            duration: Request duration in milliseconds
            status_code: HTTP status code
            properties: Additional custom properties (correlation_id, user_id, etc.)
        """
        if not self.enabled or not self.tracer:
            return
        
        try:
            # Record request duration
            attributes = {
                SpanAttributes.HTTP_STATUS_CODE: status_code,
                "http.route": name,
            }
            
            if properties:
                attributes.update({k: str(v) for k, v in properties.items()})
            
            if self.request_duration:
                self.request_duration.record(duration, attributes=attributes)
            
            if self.request_counter:
                self.request_counter.add(1, attributes=attributes)
        except Exception as e:
            logger.error(f"Failed to track request: {e}")
    
    def track_exception(
        self,
        exception: Exception,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track an exception with stack trace.
        
        Args:
            exception: The exception to track
            properties: Additional context (correlation_id, user_id, etc.)
        """
        if not self.enabled or not self.tracer:
            return
        
        try:
            # Get current span and record exception
            span = trace.get_current_span()
            if span:
                span.record_exception(exception)
                span.set_status(Status(StatusCode.ERROR, str(exception)))
                
                if properties:
                    for key, value in properties.items():
                        span.set_attribute(key, str(value))
            
            # Also log the exception
            logger.error(
                f"Exception: {type(exception).__name__}: {str(exception)}",
                exc_info=exception,
                extra={"properties": properties or {}}
            )
        except Exception as e:
            logger.error(f"Failed to track exception: {e}")
    
    def track_dependency(
        self,
        name: str,
        dependency_type: str,
        duration: float,
        success: bool,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track a dependency call (external service, database, etc.).
        
        Args:
            name: Dependency name (e.g., "Redis GET", "Supabase Query")
            dependency_type: Type of dependency (redis, http, sql, etc.)
            duration: Call duration in milliseconds
            success: Whether the call succeeded
            properties: Additional properties (query, endpoint, etc.)
        """
        if not self.enabled or not self.tracer:
            return
        
        try:
            attributes = {
                "dependency.type": dependency_type,
                "dependency.name": name,
                "success": success,
            }
            
            if properties:
                attributes.update({k: str(v) for k, v in properties.items()})
            
            if self.dependency_duration:
                self.dependency_duration.record(duration, attributes=attributes)
        except Exception as e:
            logger.error(f"Failed to track dependency: {e}")
    
    def track_metric(
        self,
        name: str,
        value: float,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track a custom metric.
        
        Args:
            name: Metric name (e.g., "cache.hit_rate", "embedding.throughput")
            value: Metric value
            properties: Additional dimensions (cache_type, project_id, etc.)
        """
        if not self.enabled or not self.meter:
            return
        
        try:
            attributes = {}
            if properties:
                attributes = {k: str(v) for k, v in properties.items()}
            
            # Use histogram to record the value
            histogram = self.meter.create_histogram(
                name=name,
                description=f"Custom metric: {name}",
                unit="1"
            )
            histogram.record(value, attributes=attributes)
        except Exception as e:
            logger.error(f"Failed to track metric: {e}")
    
    def track_event(
        self,
        name: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track a custom event.
        
        Args:
            name: Event name (e.g., "job.completed", "cache.warmed")
            properties: Event properties (job_id, duration, etc.)
        """
        if not self.enabled:
            return
        
        try:
            # Log event with properties
            logger.info(
                f"Event: {name}",
                extra={"properties": properties or {}}
            )
            
            # Also add as span event if in active span
            span = trace.get_current_span()
            if span:
                attributes = {}
                if properties:
                    attributes = {k: str(v) for k, v in properties.items()}
                span.add_event(name, attributes=attributes)
        except Exception as e:
            logger.error(f"Failed to track event: {e}")
    
    def track_cache_hit_rate(
        self,
        hit_rate: float,
        cache_type: str = "general",
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track cache hit rate metric.
        
        Args:
            hit_rate: Cache hit rate as a percentage (0-100)
            cache_type: Type of cache (embedding, query, vector_search, etc.)
            properties: Additional properties (project_id, etc.)
        """
        if not self.enabled or not self.meter:
            return
        
        try:
            attributes = {"cache_type": cache_type}
            if properties:
                attributes.update({k: str(v) for k, v in properties.items()})
            
            # Create or use existing cache hit rate gauge
            cache_hit_rate_gauge = self.meter.create_gauge(
                name="cache.hit_rate",
                description="Cache hit rate percentage",
                unit="%"
            )
            cache_hit_rate_gauge.set(hit_rate, attributes=attributes)
            
            logger.debug(f"Tracked cache hit rate: {hit_rate:.2f}% for {cache_type}")
        except Exception as e:
            logger.error(f"Failed to track cache hit rate: {e}")
    
    def track_job_queue_length(
        self,
        queue_length: int,
        job_type: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track job queue length metric.
        
        Args:
            queue_length: Current number of jobs in queue
            job_type: Type of job (optional)
            properties: Additional properties (project_id, etc.)
        """
        if not self.enabled or not self.job_queue_length:
            return
        
        try:
            attributes = {}
            if job_type:
                attributes["job_type"] = job_type
            if properties:
                attributes.update({k: str(v) for k, v in properties.items()})
            
            # Record queue length using up-down counter
            self.job_queue_length.add(queue_length, attributes=attributes)
            
            logger.debug(f"Tracked job queue length: {queue_length}")
        except Exception as e:
            logger.error(f"Failed to track job queue length: {e}")
    
    def track_embedding_throughput(
        self,
        embeddings_per_second: float,
        batch_size: int,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track embedding throughput metric.
        
        Args:
            embeddings_per_second: Number of embeddings generated per second
            batch_size: Size of the batch processed
            properties: Additional properties (model, cache_hit_rate, etc.)
        """
        if not self.enabled or not self.meter:
            return
        
        try:
            attributes = {"batch_size": str(batch_size)}
            if properties:
                attributes.update({k: str(v) for k, v in properties.items()})
            
            # Create embedding throughput histogram
            embedding_throughput = self.meter.create_histogram(
                name="embedding.throughput",
                description="Embedding generation throughput (embeddings per second)",
                unit="embeddings/s"
            )
            embedding_throughput.record(embeddings_per_second, attributes=attributes)
            
            logger.debug(
                f"Tracked embedding throughput: {embeddings_per_second:.2f} embeddings/s "
                f"(batch_size={batch_size})"
            )
        except Exception as e:
            logger.error(f"Failed to track embedding throughput: {e}")

    @contextmanager
    def start_span(
        self,
        operation_name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        properties: Optional[Dict[str, Any]] = None
    ):
        """
        Start a trace span for distributed tracing.
        
        Args:
            operation_name: Name of the operation
            kind: Span kind (INTERNAL, CLIENT, SERVER, PRODUCER, CONSUMER)
            properties: Additional span attributes
        
        Yields:
            Span object for adding attributes
        
        Example:
            with telemetry.start_span("embedding_generation") as span:
                span.set_attribute("text_length", len(text))
                result = await generate_embedding(text)
        """
        if not self.enabled or not self.tracer:
            yield None
            return
        
        try:
            with self.tracer.start_as_current_span(
                operation_name,
                kind=kind
            ) as span:
                if properties:
                    for key, value in properties.items():
                        span.set_attribute(key, str(value))
                yield span
        except Exception as e:
            logger.error(f"Failed to create span: {e}")
            yield None
    
    def flush(self) -> None:
        """Flush all pending telemetry data."""
        if not self.enabled:
            return
        
        try:
            # Force flush tracer provider
            tracer_provider = trace.get_tracer_provider()
            if hasattr(tracer_provider, 'force_flush'):
                tracer_provider.force_flush()
            
            # Force flush meter provider
            meter_provider = metrics.get_meter_provider()
            if hasattr(meter_provider, 'force_flush'):
                meter_provider.force_flush()
        except Exception as e:
            logger.error(f"Failed to flush telemetry: {e}")


class AdaptiveSampler(Sampler):
    """
    Adaptive sampler that samples 100% of errors and 10% of successful requests.

    Implements the OpenTelemetry Sampler interface so it can be passed directly
    to TracerProvider.  Errors (HTTP status >= 400) are always sampled; all
    other spans use a 10% TraceIdRatioBased sampler wrapped in ParentBased so
    that child spans honour the parent's sampling decision.
    """

    def __init__(self):
        self.success_sampler = ParentBased(root=TraceIdRatioBased(0.1))
        self.error_sampler = ALWAYS_ON

    def should_sample(  # type: ignore[override]
        self,
        parent_context: Optional[Any],
        trace_id: int,
        name: str,
        kind: Optional[Any] = None,
        attributes: Optional[Any] = None,
        links: Optional[Any] = None,
        trace_state: Optional[Any] = None,
    ) -> SamplingResult:
        """
        Determine if a span should be sampled.

        Always samples spans that carry an HTTP status >= 400; samples 10% of
        everything else.
        """
        if attributes:
            status_code = attributes.get("http.status_code") or attributes.get("http.response.status_code")
            if status_code:
                try:
                    if int(status_code) >= 400:
                        return self.error_sampler.should_sample(
                            parent_context, trace_id, name, kind=kind,
                            attributes=attributes, links=links, trace_state=trace_state
                        )
                except (ValueError, TypeError):
                    pass

        return self.success_sampler.should_sample(
            parent_context, trace_id, name, kind=kind,
            attributes=attributes, links=links, trace_state=trace_state
        )

    def get_description(self) -> str:
        """Return a human-readable description of this sampler."""
        return "AdaptiveSampler(success=10%, errors=100%)"


# Global telemetry service instance
_telemetry_service: Optional[TelemetryService] = None


def get_telemetry_service() -> TelemetryService:
    """
    Get the global telemetry service instance.
    
    Returns:
        TelemetryService instance
    """
    global _telemetry_service
    if _telemetry_service is None:
        _telemetry_service = TelemetryService()
    return _telemetry_service


def initialize_telemetry(
    connection_string: Optional[str] = None,
    service_name: str = "lumina-backend",
    service_version: str = "1.0.0"
) -> TelemetryService:
    """
    Initialize the global telemetry service.
    
    Args:
        connection_string: Azure Application Insights connection string
        service_name: Name of the service for telemetry
        service_version: Version of the service
    
    Returns:
        Initialized TelemetryService instance
    """
    global _telemetry_service
    _telemetry_service = TelemetryService(
        connection_string=connection_string,
        service_name=service_name,
        service_version=service_version
    )
    return _telemetry_service
