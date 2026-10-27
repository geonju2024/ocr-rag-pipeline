# OCR-RAG 파이프라인

PC 대시보드의 QR을 휴대폰으로 스캔 → 휴대폰 카메라가 컨베이어 화면을 찍어 서버로 전송 →
OCR → 임베딩·벡터DB 저장 → 대시보드에 실시간 현황 + RAG 질의응답.

## 실행

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app
```

- PC: `https://localhost:8443/` (처음 한 번 "안전하지 않음 → 계속")
- 휴대폰: 대시보드의 QR 스캔 (PC와 같은 Wi-Fi, 처음 한 번 "안전하지 않음 → 계속")
- 인증서는 첫 실행 때 `certs/`에 자동 생성됩니다. LAN IP가 바뀌면 다시 만들어집니다.
- 휴대폰에서 접속이 안 되면 관리자 PowerShell에서 `powershell -ExecutionPolicy Bypass -File scripts\allow-firewall.ps1`
- LAN IP 자동 탐지가 틀리거나 터널을 쓸 때는 `.env.example`을 `.env`로 복사해 `PUBLIC_HOST` / `PUBLIC_BASE_URL` 지정

### 휴대폰 없이 테스트

```powershell
# 대시보드 QR 아래 주소를 그대로 넣으면 "연결됨"까지 확인
python scripts/fake_pipeline.py --url "https://192.168.0.12:8443/m?sid=...&t=..."
```

## 파일 소유

| 담당 | 파일 |
| --- | --- |
| A ① QR · ⑤ 현황 | `app/events.py` `app/session.py` `app/status.py` `app/netinfo.py` `static/dashboard.html` `static/css/common.css` `static/js/qr.js` `static/js/status.js` `static/js/mobile-session.js` `scripts/` |
| B ② 영상 | `app/capture.py` `static/js/camera.js` |
| C ③ OCR · ④ 저장 | `app/ocr.py` `app/store.py` |
| D ⑥ RAG | `app/rag.py` `static/js/rag.js` (`#zone-rag` 안만) |
| 공용 | `app/main.py`(라우터 등록만) `requirements.txt` — 줄 추가만 |

B·C·D 파일은 지금 **합의된 형식만 맞춘 가짜 구현**입니다. 각자 실제 구현으로 교체하세요.
`data/passages.json`은 `ocr-conveyor-test.html`의 카드 100장 원문(정답 데이터)입니다.

## 약속 (자세한 내용은 합의 문서)

**이벤트 버스**: 단계가 끝날 때 `await events.publish(sid, {"type": ..., ...})`.
`sid`·`ts`(epoch ms)는 자동으로 채워집니다. 스레드풀 안에서는 `events.publish_threadsafe(sid, {...})`.

| type | 보내는 쪽 | 필드 |
| --- | --- | --- |
| `session.paired` / `session.disconnected` | B | — |
| `frame.received` | B | `bytes` |
| `frame.dropped` | B·C | `count`(생략 시 1) |
| `ocr.done` | C | `frame_ts` `chars` `conf` `ms` |
| `doc.saved` | C | `doc_id` `card_no` `title` `preview` `chars` `ms` |
| `doc.duplicate` | C | `doc_id` |
| `error` | 누구나 | `stage` `msg` |

**함수**

- `session.verify(sid, token) -> bool` — `/ws/camera` 연결 직후 호출, False면 close code `4401`
- `ocr.submit(sid, jpeg: bytes, ts: int)` — 바로 돌아오고 처리는 뒤에서
- `store.count() -> int`, `store.recent(n) -> list[dict]`, `store.search(query, k) -> list[dict]`
- `POST /api/ask {"question"}` → `{"answer", "sources": [{"card_no", "title"}]}`

**대시보드 API (A)**

- `POST /api/sessions` → `{session_id, token, mobile_url, qr_url, expires_at}`
- `GET /api/sessions/{sid}[?t=]` → 상태 (`t`를 주면 접속 가능 여부도, 토큰은 소모하지 않음)
- `GET /api/sessions/{sid}/qr.svg`
- `GET /api/status` → 스냅샷 `{count, total, recent, stats, session}`
- `WS /ws/dashboard?sid=` → 스냅샷 1회, 이후 이벤트 + 1초마다 `stats`
- 대시보드 JS는 받은 메시지를 `document`의 `pipeline:event`로 다시 뿌립니다 (rag.js 등에서 구독 가능)

## Git

`main`에 바로 push하지 않고 `feat/<기능>` 브랜치 → PR. 시작 전과 PR 전에 `git pull --rebase origin main`.
