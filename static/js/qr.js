// ① QR 카메라 연동 (담당: A)
//
// 새로고침해도 같은 QR을 유지하려고 세션을 sessionStorage에 둡니다.
// 아직 아무도 스캔하지 않은 QR이 만료되면 자동으로 새로 만듭니다.
(() => {
  const $ = (id) => document.getElementById(id);
  const KEY = 'ocr-rag.session';

  let current = null;     // POST /api/sessions 응답
  let status = 'waiting'; // waiting | paired | disconnected | expired
  let timer = null;

  function load() {
    try { return JSON.parse(sessionStorage.getItem(KEY)); } catch { return null; }
  }
  function save(s) {
    try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch { /* 저장 못 해도 동작 */ }
  }

  async function createSession() {
    const res = await fetch('/api/sessions', { method: 'POST' });
    if (!res.ok) throw new Error('세션 생성 실패 ' + res.status);
    return res.json();
  }

  async function fetchState(sid) {
    const res = await fetch(`/api/sessions/${encodeURIComponent(sid)}`);
    return res.ok ? res.json() : { status: 'expired' };
  }

  function setStatus(next, expiresAt) {
    status = next;
    if (expiresAt) current.expires_at = expiresAt;
    const badge = $('qr-badge');
    const label = { waiting: '스캔 대기', paired: '연결됨', disconnected: '연결 끊김', expired: '만료' }[next];
    badge.textContent = label;
    badge.className = 'badge ' + ({ paired: 'ok', disconnected: 'warn', expired: 'bad' }[next] ?? '');
    $('qr-box').classList.toggle('paired', next === 'paired');
    tick();
  }

  function tick() {
    const hint = $('qr-hint');
    if (status === 'paired') { hint.textContent = '휴대폰 카메라가 연결되었습니다'; return; }
    if (status === 'disconnected') { hint.textContent = '휴대폰에서 다시 접속하거나 새 QR을 만드세요'; return; }
    const left = Math.max(0, Math.round((current.expires_at - Date.now()) / 1000));
    if (left === 0) { renew(); return; }
    hint.textContent = `휴대폰 카메라로 스캔하세요 · ${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
  }

  function show(s) {
    current = s;
    save(s);
    $('qr-img').src = s.qr_url;
    $('qr-url').textContent = s.mobile_url;
    window.pipeline.connect(s.session_id);
  }

  async function renew() {
    clearInterval(timer);
    $('qr-badge').textContent = '준비 중';
    try {
      show(await createSession());
      setStatus('waiting');
    } catch (e) {
      $('qr-hint').textContent = e.message;
    }
    timer = setInterval(tick, 1000);
  }

  async function init() {
    const saved = load();
    if (saved) {
      const st = await fetchState(saved.session_id).catch(() => ({ status: 'expired' }));
      if (st.status !== 'expired') {
        show(saved);
        setStatus(st.status, st.expires_at);
        timer = setInterval(tick, 1000);
        return;
      }
    }
    renew();
  }

  document.addEventListener('pipeline:event', (e) => {
    const ev = e.detail;
    if (!current) return;
    if (ev.type === 'snapshot' && ev.session) {
      if (ev.session.status === 'expired' && status !== 'paired') renew();
      else if (ev.session.status !== 'expired') setStatus(ev.session.status, ev.session.expires_at);
    } else if (ev.type === 'session.paired' && ev.sid === current.session_id) {
      setStatus('paired');
    } else if (ev.type === 'session.disconnected' && ev.sid === current.session_id) {
      setStatus('disconnected');
    }
  });

  $('qr-new').addEventListener('click', renew);
  init();
})();
