"""
Custom validators for request validation.
"""
from typing import Any
from uuid import UUID

from pydantic import ValidationInfo, field_validator


class UUIDValidator:
    """Validator for UUID fields."""
    
    @staticmethod
    def validate_uuid(value: Any) -> UUID:
        """Validate UUID format."""
        if isinstance(value, UUID):
            return value
        
        try:
            return UUID(str(value))
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid UUID format: {value}")


class ContentValidator:
    """Validator for memory content."""
    
    @staticmethod
    def validate_content_length(value: str, max_length: int = 10000) -> str:
        """Validate content length."""
        if len(value) > max_length:
            raise ValueError(f"Content exceeds maximum length of {max_length} characters")
        
        if not value.strip():
            raise ValueError("Content cannot be empty or whitespace only")
        
        return value.strip()


class ConfidenceValidator:
    """Validator for confidence scores."""
    
    @staticmethod
    def validate_confidence(value: float) -> float:
        """Validate confidence is between 0 and 1."""
        if not 0.0 <= value <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return value


class TTLValidator:
    """Validator for TTL values."""
    
    @staticmethod
    def validate_ttl(value: int) -> int:
        """Validate TTL is positive."""
        if value <= 0:
            raise ValueError("TTL must be greater than 0")
        
        # Max TTL: 1 year
        max_ttl = 365 * 24 * 60 * 60
        if value > max_ttl:
            raise ValueError(f"TTL cannot exceed {max_ttl} seconds (1 year)")
        
        return value


class TopKValidator:
    """Validator for top_k parameter."""
    
    @staticmethod
    def validate_top_k(value: int, max_value: int = 100) -> int:
        """Validate top_k is within acceptable range."""
        if value < 1:
            raise ValueError("top_k must be at least 1")
        
        if value > max_value:
            raise ValueError(f"top_k cannot exceed {max_value}")
        
        return value
