"""
FastAPI web app — upload/OCR → review → generate → gallery.

User flow:
  GET  /              Upload screenshot (or link to /paste)
  POST /ocr           Save image, run Tesseract, show review form
  GET  /paste           Skip OCR; type/paste passage manually
  POST /generate        LLM scene brief + image → redirect to result
  GET  /result/{id}     Show image and interpretation
  GET  /gallery         Past scenes
"""

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import DEMO_MODE, GENERATED_DIR, OPENAI_API_KEY, ROOT, UPLOAD_DIR
from app.gallery import add_entry, get_entry, list_entries
from app.http_client import format_api_error
from app.ocr import OcrError, extract_text
from app.openai_client import get_openai_client
from app.scene import build_scene_brief, generate_image

app = FastAPI(title="Book Scene Viz", version="0.1.0")
templates = Jinja2Templates(directory=str(ROOT / "templates"))
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


def _save_upload(upload: UploadFile) -> Path:
    """Write uploaded screenshot to data/uploads with a unique filename."""
    suffix = Path(upload.filename or "page.png").suffix or ".png"
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    with dest.open("wb") as out:
        shutil.copyfileobj(upload.file, out)
    return dest


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Home: upload a page screenshot to start the OCR pipeline."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {"demo_mode": DEMO_MODE},
    )


@app.get("/paste", response_class=HTMLResponse)
async def paste_text(request: Request):
    """Skip OCR — useful when Tesseract is not installed or for quick API testing."""
    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "error": None,
            "passage": "",
            "upload_filename": "",
            "demo_mode": DEMO_MODE,
        },
    )


@app.post("/ocr", response_class=HTMLResponse)
async def ocr_step(
    request: Request,
    screenshot: UploadFile = File(...),
):
    """Step 1: persist upload and extract text; always show review page (even on OCR error)."""
    path = _save_upload(screenshot)
    error = None
    text = ""
    try:
        text = extract_text(path)
    except OcrError as exc:
        error = str(exc)

    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "error": error,
            "passage": text,
            "upload_filename": path.name,
            "demo_mode": DEMO_MODE,
        },
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate_step(
    request: Request,
    book_title: str = Form(...),
    author: str = Form(...),
    passage: str = Form(...),
    upload_filename: str = Form(""),
):
    """
    Step 2: validate form → scene brief → image → save gallery entry.

    Re-renders review.html on validation or API errors so the user keeps their text.
    """
    book_title = book_title.strip()
    author = author.strip()
    passage = passage.strip()

    if not book_title or not author:
        return templates.TemplateResponse(
            request,
            "review.html",
            {
                "error": "Book title and author are required.",
                "passage": passage,
                "upload_filename": upload_filename,
                "book_title": book_title,
                "author": author,
                "demo_mode": DEMO_MODE,
            },
            status_code=400,
        )
    if len(passage) < 20:
        return templates.TemplateResponse(
            request,
            "review.html",
            {
                "error": "Passage is too short. Edit the OCR text or try another photo.",
                "passage": passage,
                "upload_filename": upload_filename,
                "book_title": book_title,
                "author": author,
                "demo_mode": DEMO_MODE,
            },
            status_code=400,
        )

    try:
        scene_brief = build_scene_brief(passage, book_title, author)
        image_prompt = scene_brief.get("image_prompt") or passage
        image_path, _remote = generate_image(image_prompt)
        entry = add_entry(
            book_title=book_title,
            author=author,
            passage=passage,
            scene_brief=scene_brief,
            image_filename=image_path.name,
            upload_filename=upload_filename or None,
        )
    except Exception as exc:  # noqa: BLE001 — surface actionable message in UI
        return templates.TemplateResponse(
            request,
            "review.html",
            {
                "error": f"Generation failed:\n{format_api_error(exc)}",
                "passage": passage,
                "upload_filename": upload_filename,
                "book_title": book_title,
                "author": author,
                "demo_mode": DEMO_MODE,
            },
            status_code=500,
        )

    # 303 redirect after POST avoids duplicate submit on refresh.
    return RedirectResponse(url=f"/result/{entry['id']}", status_code=303)


@app.get("/result/{entry_id}", response_class=HTMLResponse)
async def result(request: Request, entry_id: str):
    """Show one generated scene (image + LLM interpretation + original passage)."""
    entry = get_entry(entry_id)
    if not entry:
        return RedirectResponse(url="/gallery", status_code=303)
    return templates.TemplateResponse(
        request,
        "result.html",
        {"entry": entry, "demo_mode": DEMO_MODE},
    )


@app.get("/health/ocr")
async def health_ocr():
    """Diagnostic: pytesseract import + tesseract binary on PATH."""
    from app.ocr import pytesseract as ocr_module  # noqa: PLC0415

    if ocr_module is None:
        return {
            "ok": False,
            "error": (
                "pytesseract not installed in this Python. "
                "Run: source .venv/bin/activate && pip install -r requirements.txt"
            ),
        }
    try:
        version = ocr_module.get_tesseract_version()
        return {"ok": True, "message": f"Tesseract {version} ready"}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": (
                "Tesseract binary not found. macOS: brew install tesseract\n\n"
                f"Technical detail: {exc}"
            ),
        }


@app.get("/health/openai")
async def health_openai():
    """Diagnostic: API key present and HTTPS reachability with current TLS settings."""
    if not OPENAI_API_KEY:
        return {"ok": False, "error": "OPENAI_API_KEY is not set"}
    try:
        client = get_openai_client()
        page = client.models.list()
        if not page.data:
            return {"ok": False, "error": "OpenAI responded but returned no models."}
        return {"ok": True, "message": "Connected to OpenAI API"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": format_api_error(exc)}


@app.get("/gallery", response_class=HTMLResponse)
async def gallery(request: Request):
    """Grid of past generations (newest first, from gallery.json)."""
    entries = list_entries()
    return templates.TemplateResponse(
        request,
        "gallery.html",
        {"entries": entries, "demo_mode": DEMO_MODE},
    )


@app.get("/media/generated/{filename}")
async def media_generated(filename: str):
    """Serve generated PNGs from data/generated/ (used by result + gallery templates)."""
    path = GENERATED_DIR / filename
    if not path.is_file():
        return RedirectResponse(url="/", status_code=302)
    from fastapi.responses import FileResponse

    return FileResponse(path)


@app.get("/media/uploads/{filename}")
async def media_uploads(filename: str):
    """Serve original uploads from data/uploads/ (shown on review page)."""
    path = UPLOAD_DIR / filename
    if not path.is_file():
        return RedirectResponse(url="/", status_code=302)
    from fastapi.responses import FileResponse

    return FileResponse(path)
