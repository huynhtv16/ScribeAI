import { chromium, type Browser, type Page } from 'playwright';
import { AudioRecorder } from './recorder.js';

type Provider = 'google-meet' | 'zoom' | 'teams';

interface AgentConfig {
  meetingUrl: string;
  displayName: string;
  provider: Provider;
  headless: boolean;
}

const config: AgentConfig = {
  meetingUrl: process.env.MEETING_URL ?? '',
  displayName: process.env.BOT_DISPLAY_NAME ?? 'ScribeAI Notes',
  provider: (process.env.MEETING_PROVIDER ?? 'google-meet') as Provider,
  headless: process.env.HEADLESS !== 'false',
};

async function resolveMeetingId(apiUrl: string): Promise<string> {
  if (process.env.MEETING_ID) return process.env.MEETING_ID;
  const meetingsResponse = await fetch(`${apiUrl}/api/meetings`);
  if (!meetingsResponse.ok) throw new Error('Không đọc được danh sách cuộc họp');
  const meetings = await meetingsResponse.json() as Array<{ id: string; status: string }>;
  const active = meetings.find(meeting => meeting.status === 'live');
  if (active) return active.id;
  const created = await fetch(`${apiUrl}/api/meetings`, { method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ title: 'Cuộc họp do ScribeAI tạo', source_language: 'auto', target_language: 'vi' }) });
  if (!created.ok) throw new Error('Không tạo được cuộc họp');
  const meeting = await created.json() as { id: string };
  await fetch(`${apiUrl}/api/meetings/${meeting.id}/status/live`, { method: 'POST' });
  return meeting.id;
}

async function joinGoogleMeet(page: Page): Promise<void> {
  await page.goto(config.meetingUrl, { waitUntil: 'domcontentloaded' });
  const name = page.getByPlaceholder(/your name/i);
  if (await name.isVisible().catch(() => false)) await name.fill(config.displayName);
  for (const label of [/turn off microphone/i, /turn off camera/i]) {
    const control = page.getByLabel(label);
    if (await control.isVisible().catch(() => false)) await control.click();
  }
  const join = page.getByRole('button', { name: /ask to join|join now/i });
  await join.click({ timeout: 20_000 });
}

async function run(): Promise<void> {
  if (!config.meetingUrl) throw new Error('MEETING_URL is required');
  let browser: Browser | undefined;
  let recorder: AudioRecorder | undefined;
  try {
    browser = await chromium.launch({ headless: config.headless, args: ['--autoplay-policy=no-user-gesture-required'] });
    const context = await browser.newContext({ permissions: [] });
    const page = await context.newPage();
    if (config.provider === 'google-meet') await joinGoogleMeet(page);
    else throw new Error(`${config.provider} adapter is not enabled yet`);
    console.log(`[agent] joined ${config.provider} as ${config.displayName}`);
    if (process.env.API_URL) {
      const meetingId = await resolveMeetingId(process.env.API_URL);
      recorder = new AudioRecorder({ apiUrl: process.env.API_URL, meetingId,
        speaker: config.displayName, audioSource: process.env.AUDIO_SOURCE ?? 'default' });
      await recorder.start();
    } else {
      console.log('[audio] bỏ qua thu âm; cần cấu hình API_URL');
    }
    await page.waitForEvent('close', { timeout: 0 });
  } finally {
    recorder?.stop();
    await browser?.close();
  }
}

run().catch(error => { console.error('[agent]', error); process.exit(1); });
