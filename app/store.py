"""벡터DB 저장 (담당: C) — 뼈대용 가짜 구현. C가 실제 구현으로 교체합니다.

합의된 함수 형식 (바꾸면 합의 문서 먼저 수정)
- count() -> int                          고유 doc_id 수
- recent(n) -> list[dict]                 최근 저장 순. 필드는 doc.saved와 동일
- search(query, k) -> list[dict]          doc_id, card_no, title, text, score
"""
from __future__ import annotations

import threading

_lock = threading.Lock()
_docs: dict[str, dict] = {}


def upsert(doc: dict) -> bool:
    """새 문서면 True, 이미 있던 doc_id면 False."""
    with _lock:
        is_new = doc["doc_id"] not in _docs
        _docs.pop(doc["doc_id"], None)  # 다시 넣어 최근 순서로
        _docs[doc["doc_id"]] = doc
        return is_new


def count() -> int:
    with _lock:
        return len(_docs)


def recent(n: int) -> list[dict]:
    keys = ("doc_id", "card_no", "title", "preview", "chars", "ms")
    with _lock:
        docs = list(_docs.values())[-n:][::-1]
    return [{k: d.get(k) for k in keys} for d in docs]


def search(query: str, k: int) -> list[dict]:
    words = {w for w in query.lower().split() if len(w) > 2}
    with _lock:
        docs = list(_docs.values())
    scored = []
    for d in docs:
        hay = (d["title"] + " " + d.get("text", "")).lower()
        score = sum(w in hay for w in words) / max(len(words), 1)
        scored.append({**{f: d.get(f) for f in ("doc_id", "card_no", "title", "text")}, "score": score})
    return sorted(scored, key=lambda r: r["score"], reverse=True)[:k]
