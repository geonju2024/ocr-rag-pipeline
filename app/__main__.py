"""`python -m app` — HTTPS(8443)로 서버 실행. 인증서는 처음 실행 때 자동 생성됩니다."""
from __future__ import annotations

import logging

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from . import netinfo  # noqa: E402  (.env를 읽은 뒤 import)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cert, key = netinfo.ensure_cert()
    port = netinfo.port()
    print(
        f"\n  대시보드 (PC)  : https://localhost:{port}/"
        f"\n  휴대폰 접속 주소: {netinfo.public_base_url()}/m"
        "\n  처음 접속 때 '안전하지 않음 → 계속'을 눌러 주세요.\n"
    )
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, ssl_certfile=str(cert), ssl_keyfile=str(key))


if __name__ == "__main__":
    main()
