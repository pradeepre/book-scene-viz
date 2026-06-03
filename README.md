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

**Real images (OpenAI):** set `OPENAI_API_KEY`, `DEMO_MODE=0`, and `OPENAI_IMAGE_MODEL=gpt-image-1`.

**Real images (local Ollama):** set `IMAGE_PROVIDER=ollama`, pull a model, then restart:

```bash
ollama pull x/flux2-klein:4b
```

In `.env`:

```env
IMAGE_PROVIDER=ollama
OLLAMA_IMAGE_MODEL=x/flux2-klein:4b
DEMO_MODE=0          # still needed for OpenAI scene brief; or keep 1 for demo text + real Ollama images
OPENAI_API_KEY=sk-...  # scene interpretation still uses OpenAI unless DEMO_MODE=1
```

Check Ollama: http://127.0.0.1:8000/health/ollama

On corporate laptops, `HTTP_PROXY` can block even `127.0.0.1` (Zscaler 403). The app bypasses the proxy for Ollama automatically.

Ollama image models require **macOS** and a recent Ollama version. First generation may take a few minutes while the model loads.

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
3. **POST /generate** — LLM scene brief + image (OpenAI or Ollama) → result page
4. **/gallery** — past generations (stored in `data/gallery.json`)

## Project layout

```
app/
  main.py      # FastAPI routes + templates
  ocr.py       # Image prep + Tesseract
  scene.py     # Scene brief + image generation (OpenAI or Ollama)
  ollama_client.py  # Local Ollama /api/generate for images
  gallery.py   # Local JSON gallery
templates/     # Jinja2 HTML
static/        # CSS
data/          # uploads, generated images, gallery.json
```

## Next steps (mobile later)

Keep `POST /generate` contract stable: `{ passage, book_title, author }` in, scene + image out. Replace upload UI with a native camera client when ready.
