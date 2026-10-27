"""가짜 휴대폰 (개발용, 담당: A)

진짜 휴대폰 없이 /ws/camera로 가짜 프레임을 보내 전체 흐름을 돌립니다.
뼈대의 가짜 ocr.py가 카드를 "읽은 척" 하므로 대시보드 숫자·피드·FPS·중복이 움직입니다.

    # 대시보드 QR 아래의 주소를 넣으면 그 세션으로 붙어 "연결됨"까지 확인
    python scripts/fake_pipeline.py --url "https://192.168.0.12:8443/m?sid=...&t=..."

    # 주소 없이 실행하면 세션을 새로 만들어 붙음 (현황 숫자만 확인)
    python scripts/fake_pipeline.py --server https://localhost:8443 --frames 60
"""
from __future__ import annotations

import argparse
import asyncio
import json
import ssl
import urllib.request
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.client import connect

# 개발용 자체서명 인증서라 검증을 끕니다.
SSL = ssl.create_default_context()
SSL.check_hostname = False
SSL.verify_mode = ssl.CERT_NONE

FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 2048 + b"\xff\xd9"


def new_session(server: str) -> tuple[str, str, str]:
    req = urllib.request.Request(f"{server}/api/sessions", method="POST")
    with urllib.request.urlopen(req, context=SSL) as res:
        s = json.load(res)
    return server, s["session_id"], s["token"]


def from_mobile_url(url: str) -> tuple[str, str, str]:
    u = urlsplit(url)
    q = parse_qs(u.query)
    return f"{u.scheme}://{u.netloc}", q["sid"][0], q["t"][0]


async def run(server: str, sid: str, token: str, fps: float, frames: int) -> None:
    ws_url = server.replace("https://", "wss://", 1) + f"/ws/camera?sid={sid}&t={token}"
    print(f"connect {ws_url}")
    async with connect(ws_url, ssl=SSL) as ws:
        sent = 0
        while frames <= 0 or sent < frames:
            await ws.send(FAKE_JPEG)
            sent += 1
            print(f"\rframes sent: {sent}", end="", flush=True)
            await asyncio.sleep(1 / fps)
    print()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", help="대시보드 QR의 휴대폰 주소 (https://.../m?sid=&t=)")
    p.add_argument("--server", default="https://localhost:8443")
    p.add_argument("--fps", type=float, default=2.5)
    p.add_argument("--frames", type=int, default=0, help="0이면 Ctrl+C까지 계속")
    a = p.parse_args()
    server, sid, token = from_mobile_url(a.url) if a.url else new_session(a.server.rstrip("/"))
    try:
        asyncio.run(run(server, sid, token, a.fps, a.frames))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
