# Book Scene Viz (web MVP)

Upload a screenshot of a paragraph from a physical book → OCR → edit text → pick book/author → generate a scene image.

## Requirements

- Python 3.11+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) on your system:
  - macOS: `brew install tesseract`
  - Ubuntu: `sudo apt install tesseract-ocr`

## Setup

```bash
cd book-scene-viz
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**Demo mode (no API key):** `.env.example` sets `DEMO_MODE=1`. You get OCR + a placeholder image and sample scene brief.

**Real images:** set `OPENAI_API_KEY` in `.env`, `DEMO_MODE=0`, and `OPENAI_IMAGE_MODEL=gpt-image-1` (new API keys often no longer support `dall-e-3`).

### "Connection error" / SSL certificate failed

Common on corporate networks that inspect HTTPS traffic. Add to `.env` and restart:

```env
OPENAI_SSL_VERIFY=0
```

Or point to your company root CA bundle (safer):

```env
SSL_CERT_FILE=/path/to/corporate-ca-bundle.pem
```

Test connectivity: `GET http://127.0.0.1:8000/health/openai`

## Run

**Use the project virtualenv** (system Python does not have the dependencies):

```bash
cd book-scene-viz
chmod +x run.sh
./run.sh
```

Or manually:

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000

Check OCR before uploading: http://127.0.0.1:8000/health/ocr

## Flow

1. **/** — upload screenshot
2. **POST /ocr** — Tesseract extracts text → review page
3. **POST /generate** — LLM scene brief + DALL·E image → result page
4. **/gallery** — past generations (stored in `data/gallery.json`)

## Project layout

```
app/
  main.py      # FastAPI routes + templates
  ocr.py       # Image prep + Tesseract
  scene.py     # Scene brief + image generation
  gallery.py   # Local JSON gallery
templates/     # Jinja2 HTML
static/        # CSS
data/          # uploads, generated images, gallery.json
```

## Next steps (mobile later)

Keep `POST /generate` contract stable: `{ passage, book_title, author }` in, scene + image out. Replace upload UI with a native camera client when ready.
