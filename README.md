# Asterdeck Studio · Research & Rehearsal Edition
**From Ideas to Impactful Presentations.**

A hackathon-ready MVP that unifies retrieval, AI-assisted content drafting, editable visual composition, motion, multilingual narration and judge rehearsal. Unlike a pure slide-text generator, it gives users explicit control of evidence, composition and presentation delivery.

## Run locally
Requires Python 3.10+ and a modern browser. Extract the ZIP, open a terminal in the `asterdeck-studio-v2` directory, then run:

```sh
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python server.py
```
Open http://localhost:8000. No API key is needed for editing, local English outline generation, browser narration, HTML export or PowerPoint export. Local outlines are generic starting points, not verified research.

## Enable Sarvam securely
1. Generate a new API key at https://dashboard.sarvam.ai/. Revoke any key previously shared in chat or committed anywhere.
2. Set the environment variables in the terminal (or your IDE's private run configuration). On macOS/Linux:

```sh
export SARVAM_API_KEY='YOUR_NEW_PRIVATE_KEY'
export SARVAM_MODEL='sarvam-105b'
export DEMO_ACCESS_CODE='YOUR_PRIVATE_DEMO_CODE'
python server.py
```
On Windows PowerShell use `$env:SARVAM_API_KEY='YOUR_NEW_PRIVATE_KEY'`, and similarly for the other variables. `.env.example` is a reference, not automatically loaded by the server. Never commit the real key, and never paste it into the application UI. The access code is a separate password for paid/demo routes; click **Access code** in the app and enter that code. It stays in memory in the browser tab. Server keys are never returned by health checks.

The backend sends Sarvam requests with the `api-subscription-key` header. Chat uses `/v1/chat/completions` with `sarvam-105b`; speech uses `/text-to-speech` with `bulbul:v3` and MP3 output. Calls may incur charges. If access or model availability changes, consult https://docs.sarvam.ai/.

## Demo flow
- **New deck:** topic, slide count, target audience, language, story type and theme. Optionally upload a document or retrieve external sources.
- **Research library:** retrieve Wikipedia search excerpts and Crossref bibliographic metadata/available abstracts. Click a source to inspect the original; select slide-level references. Citations are restricted to retrieved IDs but do not guarantee that a claim is supported. Metadata-only results do not validate numerical claims. Review all claims before presenting.
- **Design engine:** ten selectable layouts (title, cards, split, process, quote, closing, timeline, comparison, chart, diagram); process/timeline/diagram share a timeline-style composition. The chart requires comparable nonnegative values and retrieved citation IDs in AI mode, otherwise it falls back to a comparison. Chart objects are editable shapes, not native chart data tables.
- **Object editing:** change text, font size, alignment, geometry, colors; add images and shapes; drag to reposition; duplicate and reorder slides. Undo/redo and browser local saving.
- **Motion:** per-object entrance effects with duration and delay, slide transitions, presenter mode. The HTML presentation export retains browser animations.
- **Narration:** editable scripts, browser speech, optional Sarvam speech in 11 languages, three voice choices, pace control, MP3 download for each slide, auto-advance after narration. Browser voices vary by device. Sarvam audio is generated on demand and cached only in memory. HTML export uses browser speech, not embedded Sarvam audio. Speaker notes remain editable in PowerPoint.
- **Quality:** flag text overflow, overlap, tiny type and off-slide objects; Auto-fit text shrinks fonts and clamps text boxes to slide bounds. This is heuristic, not a guarantee of design quality.
- **Pitch coach:** generate four likely judge questions, suggested answers and three improvement ideas from the current deck using Sarvam.

## Deploy on Render
1. Create a private or public GitHub repository named `asterdeck-studio`, then upload the **contents** of the project folder. Do not upload real credentials.
2. In Render, create a Blueprint from the repository (or create a Python Web Service manually).
3. Use `pip install -r requirements.txt` as build command and `python server.py` as start command. The included `render.yaml` specifies these and the `/api/health` health check.
4. Set `SARVAM_API_KEY` to a new key and `DEMO_ACCESS_CODE` to a private access code in Render's environment settings. `SARVAM_MODEL` defaults to `sarvam-105b`. The server reads Render's `PORT` automatically.
5. Deploy and open the URL Render actually provides. Use the private access code for AI features. Check the generation, research, speech and export workflow before presenting to judges.

Render and GitHub accounts are not connected in the development environment. No public deployment has been made. Hosting plans and API billing may apply.

## Tests
```sh
python smoke_test.py
python engine_test.py
```
Smoke tests exercise the local server, document extraction, editable PPTX shapes, source notes, transition XML and missing-key handling. Contract tests mock external services (no charges). JavaScript syntax was also checked. Live browser interaction was blocked in the development environment, and real Sarvam and retrieval calls were not verified. Test with your browser and rotated key before the hackathon.

## What is not implemented yet
Native PowerPoint object animation timing and embedded MP3 playback; true video export; custom image generation; full web crawling; scanned PDF OCR; collaborative cloud editing; accounts and durable cloud database; verified fact-checking. The app is a single-user hackathon MVP with local browser storage. A simple access-code gate and process-local rate limiter protect paid endpoints but are not full authentication or production-grade abuse prevention. Do not upload private documents without permission: the extracted content is sent to Sarvam when AI generation is requested. Research queries go to the retrieval providers. A public release needs stricter security, quotas, monitoring, privacy policy and operational testing.

## Judge pitch
**Most presentation generators stop at slide creation. Asterdeck connects evidence, editable visual composition and confident delivery.** Its differentiator is an end-to-end design and rehearsal workflow: source-aware generation, layout-aware editable slides, motion, multilingual voice narration and a judge-oriented coach. Demonstrate these on a short deck and compare task completion time against your own manual workflow; do not claim unmeasured performance gains.