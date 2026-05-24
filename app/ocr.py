"""
Extract text from page photos using Tesseract OCR.

Requires:
  - Python package: pytesseract (pip)
  - System binary: tesseract (brew / apt)

Photos from phone cameras often need preprocessing (grayscale, contrast, sharpen)
before OCR accuracy is acceptable.
"""

from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

# Optional import: app still starts if pytesseract missing (OCR route shows help text).
try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None


class OcrError(Exception):
    """User-facing OCR failure (missing deps, bad photo, empty result)."""


def _prepare_image(path: Path) -> Image.Image:
    """Normalize a book-page photo for Tesseract (orientation, contrast, sharpness)."""
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)  # Respect phone rotation metadata
    image = image.convert("L")              # Grayscale reduces noise for printed text
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.SHARPEN)
    return image


def extract_text(image_path: Path) -> str:
    """
    Run OCR on a saved upload and return cleaned paragraph text.

    PSM 6 = assume a single uniform block of text (typical for one paragraph crop).
    """
    if pytesseract is None:
        raise OcrError(
            "Python package 'pytesseract' is not available in this Python environment.\n\n"
            "From the project folder, run:\n"
            "  source .venv/bin/activate\n"
            "  pip install -r requirements.txt\n"
            "  uvicorn app.main:app --reload --port 8000\n\n"
            "Or start with: ./run.sh"
        )

    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        raise OcrError(
            "Tesseract OCR is not available. Install it:\n"
            "  macOS: brew install tesseract\n"
            "  Ubuntu: sudo apt install tesseract-ocr"
        ) from exc

    image = _prepare_image(image_path)
    text = pytesseract.image_to_string(image, config="--psm 6")
    # Drop blank lines; user can fix remaining errors on the review page
    cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not cleaned:
        raise OcrError("No text detected. Try a clearer, flatter photo with good lighting.")
    return cleaned
