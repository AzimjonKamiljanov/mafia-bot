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
