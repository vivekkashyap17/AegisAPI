import random

from app.services.anomaly import analyze_event, BUFFER_SIZE


async def test_model_not_ready_before_buffer_fills(fake_redis, patch_model, make_event):
    r = await analyze_event(fake_redis, make_event())
    assert r["model_ready"] is False
    assert r["anomaly_detected"] is False
    assert r["anomaly_score"] == 0.0


async def test_trains_at_buffer_size_and_flags_attack(fake_redis, patch_model, make_event):
    random.seed(7)
    endpoints = ["/home", "/items", "/profile", "/search"]

    last = None
    for _ in range(BUFFER_SIZE):  # 100 normal events
        e = make_event(
            endpoint=random.choice(endpoints),
            method=random.choice(["GET", "POST"]),
            response_time=random.uniform(20, 90),
            status_code=200,
            payload_size=random.randint(100, 600),
        )
        last = await analyze_event(fake_redis, e)

    # model trains exactly when the buffer first reaches BUFFER_SIZE
    assert last["model_ready"] is True
    assert patch_model.exists()

    attack = make_event(
        endpoint="/admin/" + "A" * 200, method="DELETE",
        response_time=9000, status_code=500, payload_size=9_000_000)
    r = await analyze_event(fake_redis, attack)
    assert r["model_ready"] is True
    assert r["anomaly_detected"] is True
    assert r["anomaly_score"] > 0


async def test_buffer_is_capped_at_buffer_size(fake_redis, patch_model, make_event):
    for _ in range(BUFFER_SIZE + 25):
        await analyze_event(fake_redis, make_event())
    assert await fake_redis.llen("anomaly:buffer") == BUFFER_SIZE
