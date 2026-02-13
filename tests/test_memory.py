"""
Sample test file for memory repository.
"""
import pytest
from uuid import uuid4

from app.models.memory import MemoryRecord, MemoryScope, MemoryType


@pytest.fixture
def sample_memory():
    """Create a sample memory record for testing."""
    return MemoryRecord(
        org_id=uuid4(),
        agent_id=uuid4(),
        scope=MemoryScope.AGENT,
        content="Test memory content",
        memory_type=MemoryType.FACT,
        confidence=0.95,
        source_agent=uuid4(),
    )


class TestMemoryModel:
    """Tests for MemoryRecord model."""
    
    def test_memory_creation(self, sample_memory):
        """Test creating a memory record."""
        assert sample_memory.content == "Test memory content"
        assert sample_memory.memory_type == MemoryType.FACT
        assert sample_memory.scope == MemoryScope.AGENT
        assert sample_memory.confidence == 0.95
    
    def test_memory_defaults(self):
        """Test default values for memory record."""
        memory = MemoryRecord(
            org_id=uuid4(),
            agent_id=uuid4(),
            content="Test",
            source_agent=uuid4(),
        )
        assert memory.memory_type == MemoryType.OTHER
        assert memory.scope == MemoryScope.AGENT
        assert memory.confidence == 1.0
        assert memory.version == 1
        assert memory.conflict_flag == False
        assert memory.is_deleted == False


# To run tests:
# pytest tests/
