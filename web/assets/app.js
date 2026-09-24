const timer = document.querySelector('#timer');
const pause = document.querySelector('#pause');
let seconds = 18 * 60 + 42;
let running = true;
setInterval(() => {
  if (!running) return;
  seconds += 1;
  timer.textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}, 1000);
pause.addEventListener('click', () => {
  running = !running;
  pause.textContent = running ? 'Ⅱ' : '▶';
  document.querySelector('.wave').style.opacity = running ? '1' : '.25';
});
document.querySelectorAll('.task').forEach(task => task.addEventListener('change', () => {
  task.style.opacity = task.querySelector('input').checked ? '.55' : '1';
}));

