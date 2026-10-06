# Demo video recorder

Records the demo video by driving the real app in a browser: it uploads files, types the questions, waits for the
real answers, opens citations and scrolls through the Metrics page. The narration appears as captions, so the video
works without a voiceover. Eval numbers in the captions are read from `/api/evals/latest`, not typed into the script.

## Run it

1. Start the app with the GPU and make sure Ollama is running with `llama3.1:8b`:
   `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build` (from the repo root)
2. Once:
   ```bash
   cd demo
   npm install
   npm run setup          # downloads Playwright's Chromium (about 150 MB)
   ```
3. Record:
   ```bash
   npm run record                    # or: npm run record -- --headed   to watch it happen
   ```

Everything lands in `demo/output/`, named after the recording time:

- `demo-<time>.mp4` if `ffmpeg` is on your PATH, otherwise `demo-<time>.webm` (encoded with the small ffmpeg that
  `npm run setup` installs with Chromium). Both upload to YouTube. Default size is 2560x1440; see `--res` below.
- `demo-<time>-script.txt`: the narration with the time each line should start, for recording a voiceover.
  Lines that are hard to fit at a normal speaking pace are marked `[tight]`.
- `demo-<time>.srt`: the same lines as subtitles, timed to this recording (upload it to YouTube as captions).

**For a voiceover**, record without the on-screen captions: `npm run record -- --no-captions`. The script and
subtitle files are still written, timed to the video.

## What it does before recording (not filmed)

- Uploads the library files from `backend/evals/data/` that are missing (Orbit docs, Harbor HTML and Word, NIST PDF).
- Deletes `orbit-install.md` and `release-notes.md` if present, because they are uploaded on camera.
- Asks one warm-up question so the models are loaded.

Your other documents are left alone. Every run starts from the same state, so you can simply run it again.

## The check at the end

Captions describe what should happen (an answer is cited, a question is refused, an attack is blocked). After
recording, the script compares that with what the app actually did and lists any scene that differed, so a
caption never claims something the video doesn't show. Re-record, or cut those parts in an editor.

Options: `--headed` (show the browser), `--no-captions` (clean video for a voiceover),
`--res=1080|1440|2160` (video height; default 1440, 2160 is 4K), `--light` (light mode),
`--url=http://host:port` (default `http://localhost:8000`; use `http://localhost:5173` for the dev server).
Scenes and captions are plain code in `record.mjs`.

## Video quality

Playwright's built-in video is encoded at 1 Mbit/s, which blurs text. `capture.mjs` records the page through the
Chrome screencast as JPEG frames (quality 95) and encodes them with ffmpeg at a high bit rate instead. The page is
laid out the same at every resolution (as if the window were 1536 px wide), so a higher `--res` gives the same
picture with sharper text. The recorder only falls back to Playwright's own video if it finds no ffmpeg at all.
