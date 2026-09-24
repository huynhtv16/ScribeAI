import { chromium, type Browser, type Page } from 'playwright';

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
  try {
    browser = await chromium.launch({ headless: config.headless, args: ['--autoplay-policy=no-user-gesture-required'] });
    const context = await browser.newContext({ permissions: [] });
    const page = await context.newPage();
    if (config.provider === 'google-meet') await joinGoogleMeet(page);
    else throw new Error(`${config.provider} adapter is not enabled yet`);
    console.log(`[agent] joined ${config.provider} as ${config.displayName}`);
    await page.waitForEvent('close', { timeout: 0 });
  } finally {
    await browser?.close();
  }
}

run().catch(error => { console.error('[agent]', error); process.exit(1); });
