"""이벤트 버스 (담당: A)

파이프라인의 각 단계가 끝날 때 한 줄로 호출합니다.

    from app import events
    await events.publish(sid, {"type": "doc.saved", "doc_id": "014", ...})

- 공통 필드 `sid`, `ts`(epoch ms)는 여기서 채웁니다. 이미 넣었다면 그 값을 씁니다.
- 스레드풀(run_in_threadpool) 안에서는 `events.publish_threadsafe(sid, {...})`를 씁니다.
- 받는 쪽(대시보드)이 느려도 보내는 쪽은 절대 기다리지 않습니다.
  구독자 큐가 꽉 차면 가장 오래된 이벤트를 버립니다.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

log = logging.getLogger(__name__)

Event = dict[str, Any]
Listener = Callable[[Event], None]

_QUEUE_SIZE = 256

_subscribers: set[asyncio.Queue[Event]] = set()
_listeners: list[Listener] = []
_loop: asyncio.AbstractEventLoop | None = None


def now_ms() -> int:
    return int(time.time() * 1000)


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    """서버 시작 시 1회 호출. publish_threadsafe가 이 루프로 이벤트를 넘깁니다."""
    global _loop
    _loop = loop


async def publish(sid: str | None, event: Event) -> Event:
    return publish_nowait(sid, event)


def publish_nowait(sid: str | None, event: Event) -> Event:
    """이벤트 루프 스레드 안의 동기 코드용."""
    if "type" not in event:
        raise ValueError("event에는 'type'이 필요합니다")
    ev = {**event, "sid": event.get("sid", sid), "ts": event.get("ts") or now_ms()}

    for listener in list(_listeners):
        try:
            listener(ev)
        except Exception:  # 리스너 하나가 실패해도 버스는 계속 돈다
            log.exception("event listener failed: %s", ev["type"])

    for q in list(_subscribers):
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        q.put_nowait(ev)
    return ev


def publish_threadsafe(sid: str | None, event: Event) -> None:
    """스레드풀 등 이벤트 루프 밖에서 호출할 때."""
    if _loop is None:
        raise RuntimeError("events.bind_loop()가 아직 호출되지 않았습니다")
    _loop.call_soon_threadsafe(publish_nowait, sid, event)


def add_listener(fn: Listener) -> None:
    """모든 이벤트를 동기적으로 받아 서버 쪽 상태(세션, 통계)를 갱신할 때 씁니다."""
    _listeners.append(fn)


class Subscription:
    """`async with events.subscribe() as q:` → `await q.get()`으로 이벤트를 받습니다."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=_QUEUE_SIZE)

    async def __aenter__(self) -> asyncio.Queue[Event]:
        _subscribers.add(self.queue)
        return self.queue

    async def __aexit__(self, *exc: object) -> None:
        _subscribers.discard(self.queue)


def subscribe() -> Subscription:
    return Subscription()
