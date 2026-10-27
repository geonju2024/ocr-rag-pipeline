"""RAG 검색 (담당: D) — 뼈대용 가짜 구현. D가 실제 구현으로 교체합니다.

`POST /api/ask {"question"}` → `{"answer", "sources": [{"card_no", "title"}]}`
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from . import store

router = APIRouter()


class AskRequest(BaseModel):
    question: str


@router.post("/api/ask")
async def ask(req: AskRequest) -> dict:
    hits = await run_in_threadpool(store.search, req.question, 3)
    hits = [h for h in hits if h["score"] > 0]
    if not hits:
        return {"answer": "(가짜 RAG) 관련 문서를 찾지 못했습니다.", "sources": []}
    return {
        "answer": "(가짜 RAG) " + hits[0]["text"],
        "sources": [{"card_no": h["card_no"], "title": h["title"]} for h in hits],
    }
