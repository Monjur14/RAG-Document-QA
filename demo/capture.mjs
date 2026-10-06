// High-quality screen capture for the demo recorder.
//
// Playwright's built-in video is encoded at 1 Mbit/s, which smears text. This captures the page through the
// Chrome DevTools screencast as near-lossless JPEG frames and encodes them with ffmpeg at a high bit rate:
//   - an ffmpeg on your PATH  -> H.264 .mp4 (plays everywhere)
//   - otherwise the ffmpeg that `npm run setup` installed alongside Playwright's Chromium -> VP8 .webm
// If neither exists, record.mjs falls back to Playwright's own (lower quality) video.

import { spawn, spawnSync } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const FPS = 30

/** Finds an ffmpeg to encode with. Returns { path, h264 } or null. */
export function findFfmpeg() {
  if (process.env.FFMPEG_PATH && existsSync(process.env.FFMPEG_PATH)) return { path: process.env.FFMPEG_PATH, h264: true }
  const system = spawnSync('ffmpeg', ['-hide_banner', '-encoders'], { encoding: 'utf8' })
  if (system.status === 0 && system.stdout.includes('libx264')) return { path: 'ffmpeg', h264: true }

  // Playwright keeps its browsers (and a small ffmpeg that can write VP8 WebM) in one folder per OS.
  const roots = [
    process.env.PLAYWRIGHT_BROWSERS_PATH,
    process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'ms-playwright'),
    join(homedir(), '.cache', 'ms-playwright'),
    join(homedir(), 'Library', 'Caches', 'ms-playwright'),
  ].filter(Boolean)
  for (const root of roots) {
    if (!existsSync(root)) continue
    for (const dir of readdirSync(root).filter((d) => d.startsWith('ffmpeg')).sort().reverse()) {
      for (const exe of ['ffmpeg-win64.exe', 'ffmpeg-linux', 'ffmpeg-mac', 'ffmpeg-mac-arm64']) {
        const p = join(root, dir, exe)
        if (existsSync(p)) return { path: p, h264: false }
      }
    }
  }
  return null
}

export class ScreenRecorder {
  constructor(ffmpeg, outBase, { width, height }) {
    this.ffmpeg = ffmpeg
    this.size = { width, height }
    this.file = `${outBase}.${ffmpeg.h264 ? 'mp4' : 'webm'}`
    this.frames = 0
    this.last = null
    this.startedAt = 0
  }

  /** Starts capturing. Resolves once the first frame has arrived; `startedAt` is time zero of the video. */
  async start(page) {
    const encode = this.ffmpeg.h264
      ? ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart']
      : ['-c:v', 'libvpx', '-deadline', 'realtime', '-cpu-used', '4', '-b:v', '12M', '-crf', '4', '-qmin', '0', '-qmax', '24', '-threads', '4']
    this.proc = spawn(this.ffmpeg.path, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', String(FPS), '-i', 'pipe:0', ...encode, this.file], {
      stdio: ['pipe', 'ignore', 'inherit'],
    })
    this.done = new Promise((resolve) => this.proc.on('close', resolve))

    this.cdp = await page.context().newCDPSession(page)
    let firstFrame
    const gotFirst = new Promise((r) => (firstFrame = r))
    this.cdp.on('Page.screencastFrame', ({ data, sessionId }) => {
      this.last = Buffer.from(data, 'base64')
      this.cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {})
      firstFrame()
    })
    await this.cdp.send('Page.startScreencast', { format: 'jpeg', quality: 95, maxWidth: this.size.width, maxHeight: this.size.height, everyNthFrame: 1 })
    await gotFirst
    this.startedAt = Date.now()

    // Chrome only sends a frame when something on screen changes. To get a steady frame rate (and a video that
    // runs exactly as long as the recording did), repeat the latest frame for every 1/30 s that has passed.
    this.timer = setInterval(() => this.#pump(), 1000 / FPS / 2)
  }

  #pump() {
    const due = Math.floor(((Date.now() - this.startedAt) * FPS) / 1000)
    while (this.frames < due) {
      this.proc.stdin.write(this.last)
      this.frames++
    }
  }

  /** Stops capturing and waits for ffmpeg to finish the file. Returns the file path. */
  async stop() {
    this.#pump()
    clearInterval(this.timer)
    await this.cdp.send('Page.stopScreencast').catch(() => {})
    this.proc.stdin.end()
    const code = await this.done
    if (code !== 0) throw new Error(`ffmpeg exited with code ${code} while writing ${this.file}`)
    return this.file
  }
}
