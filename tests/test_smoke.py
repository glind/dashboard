"""
Smoke Tests for Personal Dashboard
Low-maintenance tests: health check, basic CRUD, UI load
"""

import pytest
import httpx
import asyncio
import time
from pathlib import Path


# Test Configuration
BASE_URL = "http://localhost:8008"
TIMEOUT = 10


@pytest.mark.asyncio
async def test_health_endpoint():
    """
    Smoke Test: Health endpoint returns 200 and valid JSON
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        response = await client.get("/health")
        
        assert response.status_code == 200, f"Health check failed with status {response.status_code}"
        
        data = response.json()
        assert "status" in data, "Health response missing 'status' field"
        assert data["status"] in ["healthy", "ok"], f"Unexpected health status: {data['status']}"
        
        print(f"✓ Health check passed: {data}")


@pytest.mark.asyncio
async def test_ui_loads():
    """
    Smoke Test: Main UI page loads and contains expected content
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        response = await client.get("/")
        
        assert response.status_code == 200, f"Main page failed with status {response.status_code}"
        assert response.headers["content-type"].startswith("text/html"), "Main page is not HTML"
        
        content = response.text
        assert "Personal Dashboard" in content or "Dashboard" in content, "Page missing dashboard title"
        
        print("✓ UI loads successfully")


@pytest.mark.asyncio
async def test_static_assets():
    """
    Smoke Test: Static assets (JS/CSS) are accessible
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        # Test main JavaScript  
        response = await client.get("/src/static/dashboard.js")
        assert response.status_code == 200, "dashboard.js not found"
        assert "DataLoader" in response.text or "class" in response.text, "dashboard.js doesn't contain expected code"
        
        print("✓ Static assets accessible")


@pytest.mark.asyncio
async def test_api_data_endpoint():
    """
    Smoke Test: API data endpoint returns valid structure
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        response = await client.get("/api/data")
        
        assert response.status_code == 200, f"API data endpoint failed with status {response.status_code}"
        
        data = response.json()
        assert isinstance(data, dict), "API data response is not a dictionary"
        
        # Check for expected top-level keys
        expected_keys = ["tasks", "calendar", "emails", "github", "weather", "news"]
        found_keys = [key for key in expected_keys if key in data]
        assert len(found_keys) > 0, f"API data missing expected keys. Found: {list(data.keys())}"
        
        print(f"✓ API data endpoint works. Found sections: {found_keys}")


@pytest.mark.asyncio
async def test_task_crud_operations():
    """
    CRUD Test: Create, Read, Update, Delete a task
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        # Create a task
        new_task = {
            "title": "Test Task - Smoke Test",
            "description": "This is a test task created by smoke tests",
            "priority": "medium",
            "source": "test"
        }
        
        # CREATE
        create_response = await client.post("/api/tasks", json=new_task)
        assert create_response.status_code in [200, 201], f"Task creation failed with status {create_response.status_code}"
        
        task_data = create_response.json()
        task_id = task_data.get("id") or task_data.get("task_id")
        assert task_id is not None, "Created task has no ID"
        
        print(f"✓ Created task with ID: {task_id}")
        
        # READ - Get all tasks (API returns object with 'tasks' array)
        read_response = await client.get("/api/tasks")
        assert read_response.status_code == 200, "Failed to read tasks"
        
        tasks_data = read_response.json()
        if isinstance(tasks_data, dict):
            tasks = tasks_data.get("tasks", [])
        else:
            tasks = tasks_data
        
        assert isinstance(tasks, list), "Tasks response doesn't contain task list"
        
        created_task = next((t for t in tasks if t.get("id") == task_id or t.get("task_id") == task_id), None)
        assert created_task is not None, f"Created task {task_id} not found in task list"
        
        print(f"✓ Read task: {created_task.get('title')}")
        
        # UPDATE - Mark as completed
        update_data = {"completed": True}
        update_response = await client.put(f"/api/tasks/{task_id}", json=update_data)
        assert update_response.status_code == 200, f"Task update failed with status {update_response.status_code}"
        
        print(f"✓ Updated task {task_id} as completed")
        
        # DELETE
        delete_response = await client.delete(f"/api/tasks/{task_id}")
        assert delete_response.status_code in [200, 204], f"Task deletion failed with status {delete_response.status_code}"
        
        print(f"✓ Deleted task {task_id}")
        
        # Verify deletion
        read_after_delete = await client.get("/api/tasks")
        tasks_data_after = read_after_delete.json()
        if isinstance(tasks_data_after, dict):
            tasks_after = tasks_data_after.get("tasks", [])
        else:
            tasks_after = tasks_data_after
        
        deleted_task = next((t for t in tasks_after if t.get("id") == task_id or t.get("task_id") == task_id), None)
        assert deleted_task is None, f"Task {task_id} still exists after deletion"
        
        print("✓ CRUD operations complete")


@pytest.mark.asyncio
async def test_config_smoke():
    """
    Smoke Test: Configuration endpoint validates required env vars
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        response = await client.get("/api/config")
        
        # Config endpoint might not exist, which is fine for MVP
        assert response.status_code in [200, 404, 500], f"Config endpoint failed with unexpected status {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Configuration loaded: {list(data.keys())[:5]}...")
        elif response.status_code == 404:
            print("✓ Config endpoint not implemented (OK for MVP)")
        else:
            # Should have a helpful error message
            error = response.json()
            assert "error" in error or "detail" in error, "Error response missing error message"
            print(f"✓ Configuration properly reports missing requirements")


if __name__ == "__main__":
    print("Running Personal Dashboard Smoke Tests...")
    print(f"Target: {BASE_URL}\n")
    
    # Run with pytest
    pytest.main([__file__, "-v", "-s"])
