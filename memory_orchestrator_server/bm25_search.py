"""BM25 全文检索（ParadeDB pg_search + jieba）。返回 {memory_id: bm25_score}，
供 repository.search() 与向量召回融合。与向量路完全独立——这里只查关键词分数。"""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 跨 name/description/content 三列做 OR 匹配，任一列命中即计分；
# paradedb.score(id) 返回该行的 BM25 相关度。project 过滤用普通 WHERE（BM25 索引含 id 主键，
# 普通列过滤由规划器结合处理）。
#
# 查询串必须经 jieba 分词后再匹配：直接 `col @@@ :q` 会把整个中文短语当单一 term，
# 与索引里分词后的 token 对不上（实测「深色模式」整串零召回，拆成「深色/模式」才命中）。
# 用 paradedb.match(field, value, tokenizer => jieba) 让查询串走与索引相同的 jieba 分词。
# tokenizer 形参是 jsonb（ParadeDB 0.23.5 实测签名），故传 '{"type":"jieba"}'::jsonb。
_BM25_SQL = text(
    """
    SELECT m.id::text AS id, paradedb.score(m.id) AS score
    FROM memories m
    WHERE m.superseded_by IS NULL
      AND m.project_id = ANY(:project_ids)
      AND (
            m.name        @@@ paradedb.match('name',        :q, tokenizer => '{"type":"jieba"}'::jsonb)
         OR m.description @@@ paradedb.match('description', :q, tokenizer => '{"type":"jieba"}'::jsonb)
         OR m.content     @@@ paradedb.match('content',     :q, tokenizer => '{"type":"jieba"}'::jsonb)
      )
    ORDER BY paradedb.score(m.id) DESC
    LIMIT :limit
    """
)


async def bm25_scores(
    session: AsyncSession,
    *,
    query: str,
    project_ids: list[uuid.UUID],
    limit: int,
) -> dict[uuid.UUID, float]:
    q = (query or "").strip()
    if not q or not project_ids:
        return {}
    result = await session.execute(
        _BM25_SQL,
        {"q": q, "project_ids": [str(p) for p in project_ids], "limit": limit},
    )
    return {uuid.UUID(row.id): float(row.score) for row in result.all()}
