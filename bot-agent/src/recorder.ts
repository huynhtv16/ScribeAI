import { spawn, type ChildProcess } from 'node:child_process';
import { watch } from 'node:fs';
import { mkdir, readFile, unlink } from 'node:fs/promises';
import path from 'node:path';

export interface RecorderConfig {
  apiUrl: string;
  meetingId: string;
  speaker: string;
  audioSource: string;
}

export class AudioRecorder {
  private process?: ChildProcess;
  private directory = path.resolve(process.env.AUDIO_CHUNK_DIR ?? '/tmp/scribeai-audio');
  private uploaded = new Set<string>();

  constructor(private config: RecorderConfig) {}

  async start(): Promise<void> {
    await mkdir(this.directory, { recursive: true });
    const output = path.join(this.directory, 'chunk-%05d.webm');
    this.process = spawn('ffmpeg', [
      '-hide_banner', '-loglevel', 'warning', '-f', 'pulse', '-i', this.config.audioSource,
      '-ac', '1', '-ar', '16000', '-c:a', 'libopus', '-f', 'segment', '-segment_time', '10',
      '-reset_timestamps', '1', output,
    ], { stdio: ['ignore', 'inherit', 'inherit'] });
    this.process.on('exit', code => console.log(`[audio] ffmpeg đã dừng (${code})`));
    watch(this.directory, (_, filename) => {
      if (!filename?.endsWith('.webm')) return;
      void this.uploadPreviousChunks(filename);
    });
    console.log(`[audio] đang thu nguồn PulseAudio: ${this.config.audioSource}`);
  }

  private async uploadPreviousChunks(activeFilename: string): Promise<void> {
    const activeNumber = Number(activeFilename.match(/\d+/)?.[0] ?? 0);
    for (let number = 0; number < activeNumber; number += 1) {
      const filename = `chunk-${String(number).padStart(5, '0')}.webm`;
      if (this.uploaded.has(filename)) continue;
      const filepath = path.join(this.directory, filename);
      try {
        const bytes = await readFile(filepath);
        const form = new FormData();
        form.append('speaker', this.config.speaker);
        form.append('file', new Blob([bytes], { type: 'audio/webm' }), filename);
        const response = await fetch(`${this.config.apiUrl}/api/meetings/${this.config.meetingId}/audio`, { method: 'POST', body: form });
        if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
        this.uploaded.add(filename);
        await unlink(filepath);
        console.log(`[audio] đã gửi ${filename}`);
      } catch (error) {
        console.error(`[audio] chưa gửi được ${filename}:`, error);
      }
    }
  }

  stop(): void { this.process?.kill('SIGTERM'); }
}
