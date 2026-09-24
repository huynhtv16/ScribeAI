const timer = document.querySelector('#timer');
const pause = document.querySelector('#pause');
const toast = document.querySelector('#toast');
const timeline = document.querySelector('#timeline');
let seconds = 18 * 60 + 42;
let running = true;
let meetingId = null;
let socket = null;
let mediaRecorder = null;
let mediaStream = null;

function notify(message) {
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2200);
}

function escapeHtml(value) {
  const element = document.createElement('div');
  element.textContent = value;
  return element.innerHTML;
}

function addSegment(segment) {
  const initials = segment.speaker.split(/\s+/).map(word => word[0]).join('').slice(0, 2).toUpperCase();
  const time = new Date(segment.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const article = document.createElement('article');
  article.className = 'segment new';
  article.innerHTML = `<span class="speaker-avatar blue">${escapeHtml(initials)}</span>
    <div class="utterance"><div class="speaker"><strong>${escapeHtml(segment.speaker)}</strong><time>${time}</time><em>${escapeHtml(segment.language.toUpperCase())}</em></div>
    <p>${escapeHtml(segment.original)}</p><p class="translated">${escapeHtml(segment.translation || 'Đang dịch…')}</p></div>
    <span class="confidence">${Math.round(segment.confidence * 100)}%</span>`;
  timeline.appendChild(article);
  timeline.scrollTop = timeline.scrollHeight;
  setTimeout(refreshInsights, 500);
}

async function uploadAudio(blob, filename = `audio-${Date.now()}.webm`) {
  if (!meetingId) throw new Error('Chưa có cuộc họp đang chạy');
  const form = new FormData();
  form.append('speaker', 'Người dùng');
  form.append('file', blob, filename);
  const response = await fetch(`/api/meetings/${meetingId}/audio`, { method: 'POST', body: form });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function refreshInsights() {
  if (!meetingId) return;
  try {
    const response = await fetch(`/api/meetings/${meetingId}/insights`);
    if (!response.ok) return;
    const data = await response.json();
    document.querySelector('#ai-summary').textContent = data.summary;
    if (data.topics.length) document.querySelector('#ai-topics').innerHTML = data.topics.map(topic => `<span>${escapeHtml(topic)}</span>`).join('');
  } catch (error) { console.error(error); }
}

async function initializeRealtime() {
  try {
    const response = await fetch('/api/meetings');
    if (!response.ok) throw new Error('Không tải được cuộc họp');
    const meetings = await response.json();
    const meeting = meetings.find(item => item.status === 'live') || meetings[0];
    if (!meeting) return;
    meetingId = meeting.id;
    document.querySelector('#meeting-title').textContent = meeting.title;
    const transcriptResponse = await fetch(`/api/meetings/${meetingId}/transcript`);
    if (transcriptResponse.ok) {
      const storedSegments = await transcriptResponse.json();
      storedSegments.forEach(addSegment);
    }
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    socket = new WebSocket(`${protocol}://${location.host}/ws/meetings/${meetingId}`);
    socket.onmessage = event => {
      const message = JSON.parse(event.data);
      if (message.type === 'segment') addSegment(message.data);
      if (message.type === 'status' && message.data.status === 'ended') notify('Cuộc họp đã kết thúc');
    };
    socket.onclose = () => setTimeout(initializeRealtime, 3000);
    await refreshInsights();
  } catch (error) {
    console.error(error);
    notify('Không thể kết nối máy chủ realtime');
  }
}

setInterval(() => {
  if (!running) return;
  seconds += 1;
  timer.textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}, 1000);

pause.addEventListener('click', () => {
  running = !running;
  pause.textContent = running ? 'Ⅱ' : '▶';
  document.querySelector('.wave').style.opacity = running ? '1' : '.25';
  notify(running ? 'Đã tiếp tục phiên âm' : 'Đã tạm dừng hiển thị');
});

document.querySelector('#share').addEventListener('click', async () => {
  await navigator.clipboard.writeText(location.href);
  notify('Đã sao chép liên kết cuộc họp');
});

document.querySelector('#end-meeting').addEventListener('click', async () => {
  if (!meetingId) return;
  const response = await fetch(`/api/meetings/${meetingId}/status/ended`, { method: 'POST' });
  if (response.ok) {
    document.querySelector('#end-meeting').disabled = true;
    notify('Đã kết thúc cuộc họp');
  }
});

document.querySelector('#upload-audio').addEventListener('click', () => document.querySelector('#audio-file').click());
document.querySelector('#audio-file').addEventListener('change', async event => {
  const file = event.target.files[0];
  if (!file) return;
  const button = document.querySelector('#upload-audio');
  button.disabled = true;
  try {
    await uploadAudio(file, file.name);
    notify('Đã xếp hàng tệp âm thanh để phiên âm');
  } catch (error) { notify(`Lỗi tải tệp: ${error.message}`); }
  finally { button.disabled = false; event.target.value = ''; }
});

document.querySelector('#record-audio').addEventListener('click', async event => {
  const button = event.currentTarget;
  if (mediaRecorder?.state === 'recording') {
    mediaRecorder.stop();
    mediaStream.getTracks().forEach(track => track.stop());
    button.classList.remove('recording');
    button.textContent = '● Thu âm';
    document.querySelector('#record-status').textContent = 'Đang xử lý đoạn âm thanh cuối…';
    return;
  }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm;codecs=opus' });
    mediaRecorder.addEventListener('dataavailable', async ({ data }) => {
      if (!data.size) return;
      try { await uploadAudio(data); notify('Đã gửi một đoạn âm thanh để phiên âm'); }
      catch (error) { notify(`Lỗi gửi âm thanh: ${error.message}`); }
    });
    mediaRecorder.addEventListener('stop', () => { document.querySelector('#record-status').textContent = 'ScribeAI sẵn sàng phiên âm theo thời gian thực'; });
    mediaRecorder.start(10000);
    button.classList.add('recording');
    button.textContent = '■ Dừng thu';
    document.querySelector('#record-status').textContent = 'Đang thu và gửi âm thanh mỗi 10 giây…';
    notify('Đã bắt đầu thu âm');
  } catch (error) { notify('Không thể truy cập micro. Hãy cấp quyền cho trình duyệt.'); }
});

document.querySelectorAll('.task').forEach(task => task.addEventListener('change', () => {
  task.style.opacity = task.querySelector('input').checked ? '.55' : '1';
}));

initializeRealtime();
