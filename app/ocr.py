"""OCR (담당: C) — 뼈대용 가짜 구현. C가 실제 구현으로 교체합니다.

합의된 함수 형식: `submit(sid, jpeg, ts)` 는 바로 돌아오고 처리는 뒤에서 합니다.
보낼 이벤트: ocr.done, doc.saved, doc.duplicate, error, frame.dropped

가짜 구현은 사진을 읽지 않고 data/passages.json의 카드를 컨베이어 순서대로
"읽은 척" 합니다. 같은 카드가 여러 프레임에 찍히는 상황(중복)도 흉내냅니다.
"""
from __future__ import annotations

import asyncio
import json
import random

from . import events, netinfo, store

_PASSAGES = json.loads((netinfo.ROOT / "data" / "passages.json").read_text(encoding="utf-8"))
_FRAMES_PER_CARD = 3

_frame_no = 0
_tasks: set[asyncio.Task] = set()


async def submit(sid: str, jpeg: bytes, ts: int) -> None:
    global _frame_no
    _frame_no += 1
    card = _PASSAGES[(_frame_no // _FRAMES_PER_CARD) % len(_PASSAGES)]
    task = asyncio.create_task(_fake_process(sid, card, ts))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _fake_process(sid: str, card: dict, frame_ts: int) -> None:
    ms = random.randint(150, 400)
    await asyncio.sleep(ms / 1000)
    if random.random() < 0.3:  # 카드가 화면 끝에 걸친 프레임 → 저장 안 함
        await events.publish(sid, {"type": "ocr.done", "frame_ts": frame_ts, "chars": 40, "conf": 0.41, "ms": ms})
        return
    text = card["text"]
    await events.publish(sid, {"type": "ocr.done", "frame_ts": frame_ts, "chars": len(text), "conf": 0.93, "ms": ms})
    doc = {
        "doc_id": card["doc_id"],
        "card_no": card["card_no"],
        "title": card["title"],
        "preview": text[:120],
        "chars": len(text),
        "ms": ms,
        "text": text,
        "sid": sid,
    }
    if store.upsert(doc):
        await events.publish(sid, {"type": "doc.saved", **{k: doc[k] for k in ("doc_id", "card_no", "title", "preview", "chars", "ms")}})
    else:
        await events.publish(sid, {"type": "doc.duplicate", "doc_id": doc["doc_id"]})
