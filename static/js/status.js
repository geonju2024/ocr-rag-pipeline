// ⑤ 실시간 저장 현황 (담당: A)
//
// 페이지의 WebSocket은 여기 하나만 엽니다. 받은 메시지는 전부
// document에 'pipeline:event'로 다시 뿌리므로, 다른 영역(qr.js, rag.js)은
//   document.addEventListener('pipeline:event', e => e.detail.type ...)
// 로 받아 쓰면 됩니다.
(() => {
  const $ = (id) => document.getElementById(id);
  const FEED_N = 6;

  let ws = null;
  let sid = null;
  let retry = 0;
  let count = 0;
  let total = 100;
  let seen = new Set();   // 같은 doc_id가 두 번 와도 숫자가 오르지 않게
  let feed = [];

  function renderCount() {
    $('st-count').textContent = count;
    $('st-total').textContent = total;
    const pct = Math.min(100, (count / total) * 100);
    $('st-bar').firstElementChild.style.width = pct + '%';
    $('st-bar').setAttribute('aria-valuenow', count);
    $('st-bar').setAttribute('aria-valuemax', total);
  }

  function renderStats(s) {
    $('st-fps').textContent = s.fps ?? 0;
    $('st-dup').textContent = s.duplicates ?? 0;
    $('st-drop').textContent = s.dropped ?? 0;
    $('st-ocr').textContent = s.ocr_ms ?? '–';
  }

  // OCR 결과(제목·본문)는 그대로 화면에 넣지 않고 textContent로만 씁니다.
  function feedItem(doc, fresh) {
    const li = document.createElement('li');
    if (fresh) li.className = 'fresh';
    const head = document.createElement('div');
    head.className = 't';
    const no = document.createElement('span');
    no.className = 'no';
    no.textContent = '#' + String(doc.card_no ?? doc.doc_id).padStart(3, '0');
    const title = document.createElement('span');
    title.className = 'title';
    title.textContent = doc.title ?? '(제목 없음)';
    const time = document.createElement('span');
    time.className = 'time';
    time.textContent = doc.ts ? new Date(doc.ts).toLocaleTimeString() : '';
    head.append(no, title, time);
    const preview = document.createElement('div');
    preview.className = 'preview';
    preview.textContent = doc.preview ?? '';
    li.append(head, preview);
    return li;
  }

  function renderFeed(freshId) {
    const ul = $('st-feed');
    ul.replaceChildren(...feed.map((d) => feedItem(d, d.doc_id === freshId)));
    if (!feed.length) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = '아직 저장된 문서가 없습니다';
      ul.append(li);
    }
  }

  function setLive(state) {
    const b = $('live-badge');
    b.textContent = { open: 'LIVE', connecting: '연결 중', closed: '재연결 중' }[state];
    b.className = 'badge ' + (state === 'open' ? 'ok' : 'warn');
  }

  function onMessage(msg) {
    switch (msg.type) {
      case 'snapshot':
        count = msg.count;
        total = msg.total;
        feed = msg.recent.slice(0, FEED_N);
        seen = new Set(feed.map((d) => d.doc_id));
        renderCount();
        renderFeed();
        renderStats(msg.stats);
        break;
      case 'doc.saved':
        if (!seen.has(msg.doc_id)) {
          seen.add(msg.doc_id);
          count += 1;
          renderCount();
        }
        feed = [msg, ...feed.filter((d) => d.doc_id !== msg.doc_id)].slice(0, FEED_N);
        renderFeed(msg.doc_id);
        break;
      case 'stats':
        renderStats(msg);
        break;
      case 'error':
        $('st-error').textContent = `[${msg.stage ?? '?'}] ${msg.msg ?? ''}`;
        break;
    }
    document.dispatchEvent(new CustomEvent('pipeline:event', { detail: msg }));
  }

  function open() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const q = sid ? `?sid=${encodeURIComponent(sid)}` : '';
    const sock = new WebSocket(`${proto}://${location.host}/ws/dashboard${q}`);
    ws = sock;
    setLive('connecting');
    sock.onopen = () => { retry = 0; setLive('open'); };
    sock.onmessage = (e) => onMessage(JSON.parse(e.data));
    sock.onclose = () => {
      if (ws !== sock) return;           // connect()로 교체된 소켓
      setLive('closed');
      retry = Math.min(retry + 1, 5);
      setTimeout(() => { if (ws === sock) open(); }, retry * 1000);
    };
  }

  // 재연결하면 서버가 스냅샷을 다시 보내 주므로 숫자가 어긋나지 않습니다.
  function connect(newSid) {
    sid = newSid;
    const old = ws;
    ws = null;
    if (old) old.close();
    open();
  }

  window.pipeline = { connect };
})();
