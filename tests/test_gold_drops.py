import time
import uuid
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from database.db import init_db
from database.models import ensure_user, get_user
from core.engine import active_drops, claim_gold_drop, cleanup_expired_drops, DEFAULT_DROP_EXPIRY_SECONDS

class MockUser:
    def __init__(self, uid, full_name):
        self.id = uid
        self.full_name = full_name
        self.first_name = full_name
        self.username = f"user_{uid}"

@pytest.mark.asyncio
async def test_concurrent_gold_drop_claims():
    await init_db()
    drop_id = f"drop_{uuid.uuid4().hex[:12]}"
    now = time.time()
    # 3 gold available, 10 users claim concurrently
    active_drops[drop_id] = {
        "id": drop_id,
        "chat_id": -9991,
        "creator_id": 111,
        "creator_name": "Sponsor",
        "total": 3,
        "remaining": 3,
        "claimed_by": {},
        "created_at": now,
        "expires_at": now + DEFAULT_DROP_EXPIRY_SECONDS
    }

    users = [MockUser(5000 + i, f"Claimer {i}") for i in range(10)]
    for u in users:
        await ensure_user(u)

    results = await asyncio.gather(*(
        claim_gold_drop(drop_id, u.id, u.full_name)
        for u in users
    ))

    successes = [r for r in results if r[0] is True]
    failures = [r for r in results if r[0] is False]

    assert len(successes) == 3, f"Expected exactly 3 claims, got {len(successes)}"
    assert len(failures) == 7
    assert active_drops[drop_id]["remaining"] == 0
    assert len(active_drops[drop_id]["claimed_by"]) == 3

@pytest.mark.asyncio
async def test_expired_gold_drop_cannot_be_claimed():
    await init_db()
    drop_id = f"drop_{uuid.uuid4().hex[:12]}"
    # Expired 20 minutes ago
    created = time.time() - 1200
    active_drops[drop_id] = {
        "id": drop_id,
        "chat_id": -9992,
        "creator_id": 112,
        "creator_name": "OldSponsor",
        "total": 5,
        "remaining": 5,
        "claimed_by": {},
        "created_at": created,
        "expires_at": created + DEFAULT_DROP_EXPIRY_SECONDS
    }

    u = MockUser(6001, "LateClaimer")
    await ensure_user(u)

    ok, msg, drop = await claim_gold_drop(drop_id, u.id, u.full_name)
    assert ok is False
    assert "tugagan" in msg.lower()
    assert active_drops[drop_id]["remaining"] == 5

@pytest.mark.asyncio
async def test_cleanup_expired_drops():
    now = time.time()
    # Drop 1: active
    id1 = f"drop_{uuid.uuid4().hex[:12]}"
    active_drops[id1] = {"id": id1, "created_at": now, "expires_at": now + 600, "remaining": 1}

    # Drop 2: expired
    id2 = f"drop_{uuid.uuid4().hex[:12]}"
    active_drops[id2] = {"id": id2, "created_at": now - 700, "expires_at": now - 100, "remaining": 2}

    purged = cleanup_expired_drops()
    assert purged >= 1
    assert id1 in active_drops
    assert id2 not in active_drops
