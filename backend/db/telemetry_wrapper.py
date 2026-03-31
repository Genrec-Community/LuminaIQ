"""
Telemetry wrapper for Supabase database operations.

This module provides a wrapper function that tracks database query telemetry
including operation type, duration, success status, and relevant properties.
"""

import time
import logging
from typing import Any, Callable, Optional
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def _null_ctx():
    """No-op context manager used when telemetry is unavailable."""
    yield None


def track_db_operation(operation_name: str, table_name: Optional[str] = None):
    """
    Decorator to track Supabase database operations with telemetry.
    
    Args:
        operation_name: Name of the database operation (e.g., "select", "insert", "update")
        table_name: Optional table name for the operation
    
    Usage:
        @track_db_operation("select", "documents")
        async def get_document(doc_id: str):
            return await async_db(lambda: client.table("documents").select("*").eq("id", doc_id).execute())
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            error_msg = None

            try:
                from core.telemetry import get_telemetry_service
                telemetry = get_telemetry_service()
            except Exception:
                telemetry = None

            span_name = f"db.{operation_name}"
            span_props = {"operation": operation_name}
            if table_name:
                span_props["table"] = table_name

            with (telemetry.start_span(span_name, properties=span_props) if telemetry else _null_ctx()) as span:
                try:
                    result = await func(*args, **kwargs)
                    success = True
                    return result
                except Exception as e:
                    error_msg = str(e)
                    if span:
                        try:
                            from opentelemetry.trace import Status, StatusCode
                            span.set_status(Status(StatusCode.ERROR, error_msg))
                            span.record_exception(e)
                        except Exception:
                            pass
                    raise
                finally:
                    duration_ms = (time.time() - start_time) * 1000

                    # Track telemetry
                    try:
                        if telemetry:
                            properties = {
                                "operation": operation_name,
                            }
                            if table_name:
                                properties["table"] = table_name
                            if error_msg:
                                properties["error"] = error_msg

                            telemetry.track_dependency(
                                name=f"Supabase {operation_name}",
                                dependency_type="supabase",
                                duration=duration_ms,
                                success=success,
                                properties=properties
                            )
                    except Exception as telemetry_err:
                        logger.debug(f"Failed to track telemetry: {telemetry_err}")
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            error_msg = None

            try:
                from core.telemetry import get_telemetry_service
                telemetry = get_telemetry_service()
            except Exception:
                telemetry = None

            span_name = f"db.{operation_name}"
            span_props = {"operation": operation_name}
            if table_name:
                span_props["table"] = table_name

            with (telemetry.start_span(span_name, properties=span_props) if telemetry else _null_ctx()) as span:
                try:
                    result = func(*args, **kwargs)
                    success = True
                    return result
                except Exception as e:
                    error_msg = str(e)
                    if span:
                        try:
                            from opentelemetry.trace import Status, StatusCode
                            span.set_status(Status(StatusCode.ERROR, error_msg))
                            span.record_exception(e)
                        except Exception:
                            pass
                    raise
                finally:
                    duration_ms = (time.time() - start_time) * 1000

                    # Track telemetry
                    try:
                        if telemetry:
                            properties = {
                                "operation": operation_name,
                            }
                            if table_name:
                                properties["table"] = table_name
                            if error_msg:
                                properties["error"] = error_msg

                            telemetry.track_dependency(
                                name=f"Supabase {operation_name}",
                                dependency_type="supabase",
                                duration=duration_ms,
                                success=success,
                                properties=properties
                            )
                    except Exception as telemetry_err:
                        logger.debug(f"Failed to track telemetry: {telemetry_err}")
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


async def track_supabase_query(operation_name: str, query_func: Callable, table_name: Optional[str] = None) -> Any:
    """
    Execute a Supabase query with telemetry tracking.
    
    Args:
        operation_name: Name of the database operation (e.g., "select", "insert", "update")
        query_func: Callable that executes the Supabase query
        table_name: Optional table name for the operation
    
    Returns:
        Query result
    
    Usage:
        result = await track_supabase_query(
            "select",
            lambda: client.table("documents").select("*").eq("id", doc_id).execute(),
            table_name="documents"
        )
    """
    start_time = time.time()
    success = False
    error_msg = None

    try:
        from core.telemetry import get_telemetry_service
        telemetry = get_telemetry_service()
    except Exception:
        telemetry = None

    span_name = f"db.{operation_name}"
    span_props = {"operation": operation_name}
    if table_name:
        span_props["table"] = table_name

    with (telemetry.start_span(span_name, properties=span_props) if telemetry else _null_ctx()) as span:
        try:
            result = query_func()
            success = True
            return result
        except Exception as e:
            error_msg = str(e)
            if span:
                try:
                    from opentelemetry.trace import Status, StatusCode
                    span.set_status(Status(StatusCode.ERROR, error_msg))
                    span.record_exception(e)
                except Exception:
                    pass
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000

            # Track telemetry
            try:
                if telemetry:
                    properties = {
                        "operation": operation_name,
                    }
                    if table_name:
                        properties["table"] = table_name
                    if error_msg:
                        properties["error"] = error_msg

                    telemetry.track_dependency(
                        name=f"Supabase {operation_name}",
                        dependency_type="supabase",
                        duration=duration_ms,
                        success=success,
                        properties=properties
                    )
            except Exception as telemetry_err:
                logger.debug(f"Failed to track telemetry: {telemetry_err}")
