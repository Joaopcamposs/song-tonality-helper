from app.services import ratelimit


def test_expired_keys_are_dropped_on_next_call(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: now[0])
    ratelimit.record("antigo")
    now[0] += ratelimit.WINDOW_SECONDS + 1
    ratelimit.record("novo")
    assert list(ratelimit._hits) == ["novo"]
    now[0] += ratelimit.WINDOW_SECONDS + 1
    assert ratelimit.exceeded("outro") is False
    assert not ratelimit._hits
