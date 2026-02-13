"""Interfaces package exports."""
from app.interfaces.repository import IRepository
from app.interfaces.service import IMemoryService

__all__ = [
    "IRepository",
    "IMemoryService",
]
