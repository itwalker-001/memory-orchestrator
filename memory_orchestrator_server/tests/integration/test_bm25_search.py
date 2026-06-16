import pytest
from memory_orchestrator_server.bm25_search import bm25_scores

pytestmark = pytest.mark.asyncio


async def test_bm25_scores_returns_keyword_hit(db_session, seeded_memories):
    """jieba BM25 命中含某关键词的记忆，返回 {memory_id: score>0}。
    seeded_memories 应至少含一条 content 提到 '深色模式' 的记忆。"""
    scores = await bm25_scores(
        db_session,
        query="深色模式",
        project_ids=[seeded_memories.project_id],
        limit=10,
    )
    assert isinstance(scores, dict)
    assert any(v > 0 for v in scores.values())


async def test_bm25_scores_empty_query_returns_empty(db_session, seeded_memories):
    scores = await bm25_scores(
        db_session, query="   ", project_ids=[seeded_memories.project_id], limit=10
    )
    assert scores == {}


async def test_bm25_scores_scopes_to_projects(db_session, seeded_memories):
    scores = await bm25_scores(
        db_session, query="深色模式", project_ids=[], limit=10
    )
    assert scores == {}


async def test_search_fusion_boosts_keyword_match(db_session, seeded_memories, repo_factory):
    """开启 bm25 后，纯关键词命中（向量未必近）的记忆应进入结果。
    repo_factory 构造 MemoryRepository；seeded_memories 含一条 content 提到独特符号
    'IdleTimer' 的记忆，但其向量与查询语义未必接近。"""
    repo = repo_factory(db_session)
    # 确保开关开启（直接写 settings）
    await repo.set_settings({"bm25_enabled": "true", "score_bm25_weight": "0.8"})
    qvec = [0.0] * 1024  # 故意给一个无意义向量，逼近全靠 BM25
    hits = await repo.search(
        query_embedding=qvec,
        project_ids=[seeded_memories.project_id],
        top_k=5,
        query="IdleTimer",
    )
    names = [h.memory.name for h in hits]
    assert any("IdleTimer" in (h.memory.content or "") for h in hits), names
