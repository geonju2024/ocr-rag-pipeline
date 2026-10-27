// 카메라·프레임 전송 (담당: B) — 뼈대용 최소 구현. B가 실제 구현으로 교체/확장합니다.
// 합의: JPEG 바이너리, 긴 변 1280px, 품질 0.8, 초당 2~3장
(() => {
  const FPS = 2.5;
  const LONG_SIDE = 1280;
  const video = document.getElementById('cam-video');
  const btn = document.getElementById('cam-start');
  const info = document.getElementById('cam-info');
  const canvas = document.createElement('canvas');
  let session = null;
  let ws = null;
  let loop = null;
  let sent = 0;

  document.addEventListener('session:ready', (e) => {
    session = e.detail;
    btn.disabled = false;
  });

  function sendFrame() {
    if (!ws || ws.readyState !== WebSocket.OPEN || ws.bufferedAmount > 0 || !video.videoWidth) return;
    const scale = Math.min(1, LONG_SIDE / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (blob && ws?.readyState === WebSocket.OPEN) {
        ws.send(blob);
        info.textContent = `보낸 프레임 ${++sent} · ${Math.round(blob.size / 1024)} KB`;
      }
    }, 'image/jpeg', 0.8);
  }

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    try {
      if (!video.srcObject) {
        video.srcObject = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
          audio: false,
        });
      }
    } catch (err) {
      session.show('카메라 권한이 필요합니다: ' + err.message, 'bad');
      btn.disabled = false;
      return;
    }
    ws = new WebSocket(session.wsUrl);
    ws.onopen = () => {
      session.show('대시보드와 연결됨 · 프레임 전송 중', 'ok');
      loop = setInterval(sendFrame, 1000 / FPS);
    };
    ws.onclose = (ev) => {
      clearInterval(loop);
      session.handleClose(ev);
      btn.disabled = ev.code === 4401;
    };
  });
})();
