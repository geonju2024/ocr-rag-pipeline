// ⑥ RAG 검색 (담당: D) — 뼈대용 최소 구현. D가 실제 구현으로 교체합니다.
// #zone-rag 안만 사용합니다. 출처는 현황 피드와 같은 `#014 How Bread Fails` 형식.
(() => {
  const zone = document.getElementById('zone-rag');
  zone.insertAdjacentHTML('beforeend', `
    <form id="rag-form" style="display:flex;gap:8px">
      <input id="rag-q" placeholder="What water temperature kills yeast?"
             style="flex:1;min-width:0;padding:6px 10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink)">
      <button>검색</button>
    </form>
    <div id="rag-answer" class="muted"></div>`);

  document.getElementById('rag-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const out = document.getElementById('rag-answer');
    out.textContent = '검색 중…';
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: document.getElementById('rag-q').value }),
    });
    const data = await res.json();
    const src = data.sources.map((s) => `#${String(s.card_no).padStart(3, '0')} ${s.title}`).join(', ');
    out.textContent = data.answer + (src ? `\n출처: ${src}` : '');
    out.style.whiteSpace = 'pre-wrap';
  });
})();
