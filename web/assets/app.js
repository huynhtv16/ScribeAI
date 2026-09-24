const timer = document.querySelector('#timer');
const pause = document.querySelector('#pause');
const toast = document.querySelector('#toast');
const timeline = document.querySelector('#timeline');
let seconds = 18 * 60 + 42;
let running = true;
let meetingId = null;
let socket = null;

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

document.querySelectorAll('.task').forEach(task => task.addEventListener('change', () => {
  task.style.opacity = task.querySelector('input').checked ? '.55' : '1';
}));

initializeRealtime();
