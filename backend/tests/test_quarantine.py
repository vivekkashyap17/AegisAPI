from app.services.quarantine import (
    quarantine_user, is_quarantined, get_quarantine, release_user,
)


async def test_not_quarantined_by_default(fake_redis):
    assert await is_quarantined(fake_redis, "u1") is False
    assert await get_quarantine(fake_redis, "u1") is None


async def test_quarantine_then_flagged(fake_redis):
    await quarantine_user(fake_redis, "u1", ttl=3600, reason="High risk with low trust")
    assert await is_quarantined(fake_redis, "u1") is True


async def test_get_quarantine_returns_reason_and_retry_after(fake_redis):
    await quarantine_user(fake_redis, "u1", ttl=900, reason="Trust score critically low")
    info = await get_quarantine(fake_redis, "u1")
    assert info is not None
    assert info["reason"] == "Trust score critically low"
    assert "quarantined_at" in info
    assert 0 < info["retry_after"] <= 900


async def test_release_removes_quarantine(fake_redis):
    await quarantine_user(fake_redis, "u1", ttl=3600, reason="x")
    assert await release_user(fake_redis, "u1") is True
    assert await is_quarantined(fake_redis, "u1") is False
    # releasing a non-quarantined subject is a no-op
    assert await release_user(fake_redis, "u1") is False


async def test_requarantine_refreshes_ttl_and_reason(fake_redis):
    await quarantine_user(fake_redis, "u1", ttl=10, reason="first")
    await quarantine_user(fake_redis, "u1", ttl=3600, reason="second")
    info = await get_quarantine(fake_redis, "u1")
    assert info["reason"] == "second"
    assert info["retry_after"] > 10
