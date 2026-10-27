"""실시간 영상 수신 (담당: B) — 뼈대용 최소 구현. B가 실제 구현으로 교체/확장합니다.

`wss://<host>:8443/ws/camera?sid=&t=`
- 연결 직후 session.verify(sid, t). 실패하면 close code 4401
- 연결되면 session.paired, 끊기면 session.disconnected
- 바이너리 메시지 = JPEG 바이트 → frame.received {bytes} → ocr.submit
"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import events, ocr, session

router = APIRouter()


@router.websocket("/ws/camera")
async def camera_ws(ws: WebSocket, sid: str = "", t: str = "") -> None:
    await ws.accept()  # 커스텀 close code를 보내려면 먼저 accept해야 합니다
    if not session.verify(sid, t):
        await ws.close(code=4401, reason="invalid or expired session")
        return
    await session.mark_paired(sid)
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            data = msg.get("bytes")
            if data:
                ts = events.now_ms()
                await events.publish(sid, {"type": "frame.received", "bytes": len(data)})
                await ocr.submit(sid, data, ts)
    except WebSocketDisconnect:
        pass
    finally:
        await session.mark_disconnected(sid)
