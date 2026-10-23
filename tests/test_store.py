import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.domain.features import ALGO_VERSION, AudioFeatures
from app.services import store
from tests.conftest import DEFAULT_TEST_URL


def _features(top_midi: int = 71) -> AudioFeatures:
    return AudioFeatures(
        top_midi=top_midi,
        ranking=[(71, 150), (67, 400)],
        top_times=[12.3],
        chroma_profile=[float(i) / 10 for i in range(12)],
    )


async def test_save_then_find_roundtrips_features():
    async with store.session() as session:
        await store.save(session, "abc", "Dois Passarinhos", 120, _features())
    async with store.session() as session:
        row = await store.find(session, "abc")
    assert row is not None
    assert store.to_features(row) == _features()
    assert (row.title, row.duration_seconds) == ("Dois Passarinhos", 120)
    assert row.algo_version == ALGO_VERSION


async def test_find_missing_returns_none():
    async with store.session() as session:
        assert await store.find(session, "nada") is None


async def test_save_overwrites_existing_video():
    async with store.session() as session:
        await store.save(session, "abc", "Antigo", 100, _features(71))
        await store.save(session, "abc", "Novo", 110, _features(72))
        rows = await store.list_recent(session)
    assert [(r.title, r.top_midi) for r in rows] == [("Novo", 72)]


async def test_list_recent_is_newest_first():
    async with store.session() as session:
        for video_id in ("a", "b", "c"):
            await store.save(session, video_id, video_id, 60, _features())
        rows = await store.list_recent(session)
    assert [r.video_id for r in rows] == ["c", "b", "a"]


async def test_tables_live_in_own_schema_on_postgres():
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        rows = await connection.execute(
            text(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_name IN ('analyses', 'jobs')"
            )
        )
        found = {tuple(row) for row in rows}
    await engine.dispose()
    assert found == {(store.SCHEMA, "analyses"), (store.SCHEMA, "jobs")}
