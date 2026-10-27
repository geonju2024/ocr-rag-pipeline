"""실시간 저장 현황 (담당: A)

- `GET /api/status?sid=`      현재 스냅샷 (새로고침 복구용)
- `WS  /ws/dashboard?sid=`    접속 직후 스냅샷 1회 → 이후 이벤트 스트림 + 1초마다 통계

"N / 100"은 세션별이 아니라 DB 전체의 고유 doc_id 수입니다 (store.count()).
FPS·버린 프레임·중복 수는 이벤트를 서버에서 모아 1초마다 보냅니다.
프레임마다 대시보드로 이벤트를 흘리지 않고, 새로고침해도 숫자가 유지되게 하기 위해서입니다.
"""
from __future__ import annotations

import asyncio
import collections
import os
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from . import events, session, store

FPS_WINDOW_S = 5.0
STATS_INTERVAL_S = 1.0
RECENT_N = 6

# 대시보드로 그대로 넘기는 이벤트. frame.* 은 통계로만 모읍니다.
FORWARD = {"doc.saved", "doc.duplicate", "ocr.done", "error"}
SESSION_EVENTS = {"session.paired", "session.disconnected"}

router = APIRouter()


def total_docs() -> int:
    return int(os.getenv("TOTAL_DOCS", "100"))


class _Stats:
    def __init__(self) -> None:
        self.frame_times: collections.deque[float] = collections.deque()
        self.frames = 0
        self.dropped = 0
        self.duplicates = 0
        self.errors = 0
        self.ocr_ms: collections.deque[int] = collections.deque(maxlen=10)

    def on_event(self, ev: events.Event) -> None:
        t = ev["type"]
        if t == "frame.received":
            self.frames += 1
            self.frame_times.append(time.monotonic())
        elif t == "frame.dropped":
            self.dropped += int(ev.get("count", 1))
        elif t == "doc.duplicate":
            self.duplicates += 1
        elif t == "error":
            self.errors += 1
        elif t == "ocr.done" and isinstance(ev.get("ms"), (int, float)):
            self.ocr_ms.append(int(ev["ms"]))

    def fps(self) -> float:
        cutoff = time.monotonic() - FPS_WINDOW_S
        while self.frame_times and self.frame_times[0] < cutoff:
            self.frame_times.popleft()
        return round(len(self.frame_times) / FPS_WINDOW_S, 1)

    def snapshot(self) -> dict:
        return {
            "type": "stats",
            "fps": self.fps(),
            "frames": self.frames,
            "dropped": self.dropped,
            "duplicates": self.duplicates,
            "errors": self.errors,
            "ocr_ms": round(sum(self.ocr_ms) / len(self.ocr_ms)) if self.ocr_ms else None,
            "ts": events.now_ms(),
        }


stats = _Stats()
events.add_listener(stats.on_event)


async def snapshot(sid: str | None) -> dict:
    count, recent = await asyncio.gather(
        run_in_threadpool(store.count), run_in_threadpool(store.recent, RECENT_N)
    )
    return {
        "type": "snapshot",
        "count": count,
        "total": total_docs(),
        "recent": recent,
        "stats": stats.snapshot(),
        "session": session.state(sid) if sid else None,
        "ts": events.now_ms(),
    }


@router.get("/api/status")
async def get_status(sid: str | None = None) -> dict:
    return await snapshot(sid)


@router.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket, sid: str | None = None) -> None:
    await ws.accept()
    try:
        # 스냅샷보다 먼저 구독해야 그 사이에 저장된 문서를 놓치지 않습니다.
        async with events.subscribe() as q:
            await ws.send_json(await snapshot(sid))
            next_tick = time.monotonic() + STATS_INTERVAL_S
            while True:
                timeout = max(0.0, next_tick - time.monotonic())
                try:
                    ev = await asyncio.wait_for(q.get(), timeout)
                except asyncio.TimeoutError:
                    await ws.send_json(stats.snapshot())
                    next_tick = time.monotonic() + STATS_INTERVAL_S
                    continue
                if ev["type"] in FORWARD or (ev["type"] in SESSION_EVENTS and ev.get("sid") == sid):
                    await ws.send_json(ev)
    except (WebSocketDisconnect, RuntimeError):
        pass
