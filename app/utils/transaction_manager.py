"""
Transaction manager utilities for coordinating database operations.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, Any, List
from functools import wraps
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class TransactionContext:
    """Context manager for handling transactions with automatic rollback."""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize transaction context.
        
        Args:
            session: Async database session
        """
        self.session = session
        self._savepoint = None
        self._before_commit_hooks: List[Callable] = []
        self._after_commit_hooks: List[Callable] = []
        self._on_rollback_hooks: List[Callable] = []
    
    def add_before_commit_hook(self, hook: Callable) -> None:
        """Add a hook to run before commit."""
        self._before_commit_hooks.append(hook)
    
    def add_after_commit_hook(self, hook: Callable) -> None:
        """Add a hook to run after successful commit."""
        self._after_commit_hooks.append(hook)
    
    def add_rollback_hook(self, hook: Callable) -> None:
        """Add a hook to run on rollback."""
        self._on_rollback_hooks.append(hook)
    
    async def _run_hooks(self, hooks: List[Callable]) -> None:
        """Run all hooks in a list."""
        for hook in hooks:
            try:
                if hasattr(hook, '__await__'):
                    await hook()
                else:
                    hook()
            except Exception as e:
                logger.error(f"Hook execution failed: {e}")
    
    async def __aenter__(self):
        """Enter transaction context."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit transaction context with cleanup."""
        if exc_type is not None:
            # Rollback on exception
            await self.session.rollback()
            await self._run_hooks(self._on_rollback_hooks)
            logger.warning(f"Transaction rolled back due to: {exc_val}")
            return False
        
        try:
            # Run before commit hooks
            await self._run_hooks(self._before_commit_hooks)
            
            # Commit transaction
            await self.session.commit()
            
            # Run after commit hooks
            await self._run_hooks(self._after_commit_hooks)
            
        except Exception as e:
            await self.session.rollback()
            await self._run_hooks(self._on_rollback_hooks)
            logger.error(f"Transaction commit failed: {e}")
            raise


@asynccontextmanager
async def transactional(session: AsyncSession) -> AsyncGenerator[TransactionContext, None]:
    """
    Context manager for explicit transaction control.
    
    Usage:
        async with transactional(session) as tx:
            tx.add_after_commit_hook(send_notification)
            # ... database operations ...
    
    Args:
        session: Async database session
    
    Yields:
        TransactionContext: Transaction context with hooks
    """
    tx = TransactionContext(session)
    async with tx:
        yield tx


@asynccontextmanager
async def with_savepoint(session: AsyncSession) -> AsyncGenerator[None, None]:
    """
    Context manager for nested transactions using savepoints.
    
    Usage:
        async with with_savepoint(session):
            # ... database operations ...
            # These will rollback to savepoint on error
    
    Args:
        session: Async database session
    
    Yields:
        None
    """
    async with session.begin_nested():
        try:
            yield
        except Exception as e:
            logger.warning(f"Savepoint rolled back: {e}")
            raise


def with_transaction(func: Callable) -> Callable:
    """
    Decorator to wrap a function in a transaction.
    
    Usage:
        @with_transaction
        async def create_memory(session: AsyncSession, data: dict):
            # ... database operations ...
            # Transaction is automatically committed/rolled back
    
    Args:
        func: Async function to wrap
    
    Returns:
        Wrapped function with transaction handling
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Find session in args or kwargs
        session = None
        for arg in args:
            if isinstance(arg, AsyncSession):
                session = arg
                break
        
        if not session:
            session = kwargs.get('session') or kwargs.get('db')
        
        if not session:
            raise ValueError("No AsyncSession found in function arguments")
        
        async with transactional(session):
            return await func(*args, **kwargs)
    
    return wrapper


def retry_on_deadlock(max_retries: int = 3, backoff_ms: int = 100):
    """
    Decorator to retry database operations on deadlock.
    
    Usage:
        @retry_on_deadlock(max_retries=3, backoff_ms=200)
        async def update_memory(session: AsyncSession, memory_id: UUID):
            # ... database operations ...
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_ms: Backoff delay in milliseconds between retries
    
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            import asyncio
            
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except SQLAlchemyError as e:
                    last_error = e
                    error_msg = str(e).lower()
                    
                    # Check if it's a deadlock error
                    if 'deadlock' in error_msg or 'lock timeout' in error_msg:
                        if attempt < max_retries - 1:
                            delay = (backoff_ms / 1000) * (attempt + 1)
                            logger.warning(
                                f"Deadlock detected, retrying in {delay}s "
                                f"(attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                    
                    # Not a deadlock or max retries reached
                    raise
            
            # Max retries reached
            logger.error(f"Transaction failed after {max_retries} attempts")
            raise last_error
        
        return wrapper
    return decorator


class DistributedTransactionCoordinator:
    """Coordinator for distributed transactions across multiple stores."""
    
    def __init__(self):
        """Initialize coordinator."""
        self._compensating_actions: List[Callable] = []
    
    def add_compensating_action(self, action: Callable) -> None:
        """
        Add a compensating action to run on rollback.
        
        Args:
            action: Async function to compensate a completed action
        """
        self._compensating_actions.append(action)
    
    async def rollback(self) -> None:
        """Execute all compensating actions in reverse order."""
        for action in reversed(self._compensating_actions):
            try:
                if hasattr(action, '__await__'):
                    await action()
                else:
                    action()
            except Exception as e:
                logger.error(f"Compensating action failed: {e}")
    
    async def commit(self) -> None:
        """Clear compensating actions after successful commit."""
        self._compensating_actions.clear()


@asynccontextmanager
async def distributed_transaction() -> AsyncGenerator[DistributedTransactionCoordinator, None]:
    """
    Context manager for distributed transactions across Postgres, Redis, and Qdrant.
    
    Usage:
        async with distributed_transaction() as dtx:
            # PostgreSQL operation
            memory = await pg_repo.create(memory_data)
            dtx.add_compensating_action(lambda: pg_repo.delete(memory.id))
            
            # Qdrant operation
            await vector_db.add(embedding, memory.id)
            dtx.add_compensating_action(lambda: vector_db.delete(memory.id))
            
            # Redis operation
            await redis.set(key, value)
            dtx.add_compensating_action(lambda: redis.delete(key))
    
    Yields:
        DistributedTransactionCoordinator: Coordinator for managing compensating actions
    """
    coordinator = DistributedTransactionCoordinator()
    try:
        yield coordinator
        await coordinator.commit()
    except Exception as e:
        logger.error(f"Distributed transaction failed: {e}")
        await coordinator.rollback()
        raise
