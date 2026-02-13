"""
Quick API test script to verify endpoints are working.
"""
import httpx
import json
import asyncio

BASE_URL = "http://localhost:8000"

async def test_health():
    """Test health endpoint."""
    print("Testing /health endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}\n")

async def test_create_memory():
    """Test creating a memory record."""
    print("Testing POST /memory/ endpoint...")
    memory_data = {
        "content": "This is a test memory from the API test script!",
        "org_id": "123e4567-e89b-12d3-a456-426614174000",  # Valid UUID
        "agent_id": "987fcdeb-51a2-43e7-9b3c-123456789abc",  # Valid UUID
        "scope": "agent",
        "memory_type": "experience",  # Valid enum value
        "metadata": {"source": "test_script", "importance": "high"}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/memory/", json=memory_data)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}\n")
        
        if response.status_code == 200:
            return response.json()
        return None

async def test_get_memory(memory_id):
    """Test retrieving a memory record."""
    print(f"Testing GET /memory/{memory_id} endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/memory/{memory_id}")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}\n")

async def main():
    print("=" * 60)
    print("memCore API Test Suite")
    print("=" * 60 + "\n")
    
    # Test 1: Health check
    await test_health()
    
    # Test 2: Create memory
    created_memory = await test_create_memory()
    
    # Test 3: Get memory (if creation succeeded)
    if created_memory and "id" in created_memory:
        await test_get_memory(created_memory["id"])
    
    print("=" * 60)
    print("Tests complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
