import os
import subprocess
import pytest
from database.models import is_admin

def test_admin_numeric_only():
    assert is_admin(8048940366) is True
    assert is_admin(7651553630) is True
    # Username spoofing must NOT grant admin access
    assert is_admin(999999999, "rasuljonovv_a") is False
    assert is_admin(111111111, "kamiljanovazimjon") is False
    assert is_admin(0) is False

def test_bot_token_fail_fast():
    # Run a subprocess with empty BOT_TOKEN to ensure it raises ValueError
    env = os.environ.copy()
    env["BOT_TOKEN"] = ""
    res = subprocess.run(
        ["python3", "-c", "import config"],
        env=env,
        capture_output=True,
        text=True
    )
    assert res.returncode != 0
    assert "BOT_TOKEN is missing or empty" in res.stderr

def test_bot_token_whitespace_fail_fast():
    env = os.environ.copy()
    env["BOT_TOKEN"] = "   "
    res = subprocess.run(
        ["python3", "-c", "import config"],
        env=env,
        capture_output=True,
        text=True
    )
    assert res.returncode != 0
    assert "BOT_TOKEN is missing or empty" in res.stderr

def test_admin_id_safe_numeric_parsing():
    env = os.environ.copy()
    env["BOT_TOKEN"] = "123:test_token"
    env["ADMIN_ID"] = "not_a_valid_number"
    res = subprocess.run(
        ["python3", "-c", "import config; assert config.ADMIN_ID == 0; print('OK')"],
        env=env,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "OK" in res.stdout

def test_admin_id_valid_numeric_parsing():
    env = os.environ.copy()
    env["BOT_TOKEN"] = "123:test_token"
    env["ADMIN_ID"] = "9988776655"
    res = subprocess.run(
        ["python3", "-c", "import config; assert config.ADMIN_ID == 9988776655; assert 9988776655 in config.ADMIN_IDS; print('OK')"],
        env=env,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "OK" in res.stdout

def test_dynamic_db_path_resolution():
    env = os.environ.copy()
    env["BOT_TOKEN"] = "123:test_token"
    env["DB_PATH"] = ":memory:"
    res = subprocess.run(
        ["python3", "-c", "import config; assert config.DB_PATH == ':memory:'; print('OK')"],
        env=env,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "OK" in res.stdout

@pytest.mark.asyncio
async def test_admin_ai_dynamic_admin_prompt(monkeypatch):
    from unittest.mock import MagicMock
    from handlers.admin_ai import query_gemini_ai
    monkeypatch.setenv("GEMINI_API_KEY", "mock_key")
    captured = {}

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, json=None):
            nonlocal captured
            captured["payload"] = json
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "AI Response"}]}}]
            }
            return mock_resp

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    res = await query_gemini_ai("Salom", admin_id=999888777)
    assert res == "AI Response"
    prompt_sent = captured["payload"]["contents"][0]["parts"][0]["text"]
    assert "ID: 999888777" in prompt_sent
    assert "7651553630" not in prompt_sent
