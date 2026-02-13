"""
Custom decorators for API endpoints.
"""
import functools
import time
from typing import Callable, Any

from fastapi import HTTPException, status
from prometheus_client import Counter, Histogram

# Metrics
request_count = Counter(
    "maas_request_total",
    "Total request count",
    ["method", "endpoint", "status"]
)

request_duration = Histogram(
    "maas_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"]
)

memory_operations = Counter(
    "maas_memory_operations_total",
    "Total memory operations",
    ["operation", "status"]
)


def track_metrics(operation: str = "unknown"):
    """
    Decorator to track metrics for memory operations.
    
    Args:
        operation: Name of the operation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            status_label = "success"
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status_label = "error"
                raise
            finally:
                duration = time.time() - start_time
                memory_operations.labels(operation=operation, status=status_label).inc()
                
        return wrapper
    return decorator


def require_org_access(func: Callable) -> Callable:
    """
    Decorator to validate organization access.
    This is a placeholder - implement proper auth logic.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # TODO: Implement actual organization access validation
        # For now, just pass through
        return await func(*args, **kwargs)
    return wrapper


def require_agent_access(func: Callable) -> Callable:
    """
    Decorator to validate agent access.
    This is a placeholder - implement proper auth logic.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # TODO: Implement actual agent access validation
        # For now, just pass through
        return await func(*args, **kwargs)
    return wrapper


def cache_result(ttl: int = 60):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time to live in seconds
    """
    cache = {}
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            current_time = time.time()
            
            # Check if cached result exists and is still valid
            if cache_key in cache:
                cached_time, cached_result = cache[cache_key]
                if current_time - cached_time < ttl:
                    return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache[cache_key] = (current_time, result)
            
            return result
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator to retry function on failure.
    
    Args:
        max_retries: Maximum number of retries
        delay: Delay between retries in seconds
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay * (attempt + 1))
                    
            raise last_exception
        return wrapper
    return decorator


import asyncio  # Import at the end to avoid issues
