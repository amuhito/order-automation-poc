from pathlib import Path

import fitz
import pdfplumber
import pytesseract
from PIL import Image


def extract_text_from_pdf(pdf_path: Path) -> dict:
    # Prefer embedded text first, then fall back to OCR for scanned pages.
    texts: list[str] = []
    page_stats: list[dict] = []

    with pdfplumber.open(pdf_path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            direct_text = (page.extract_text() or "").strip()
            if direct_text:
                texts.append(f"[PAGE {index}]\n{direct_text}")
                page_stats.append({"page": index, "mode": "direct-text", "chars": len(direct_text)})
                continue

            with fitz.open(pdf_path) as doc:
                pix = doc[index - 1].get_pixmap(matrix=fitz.Matrix(2, 2))
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_text = run_tesseract(image)
                texts.append(f"[PAGE {index}]\n{ocr_text}")
                page_stats.append({"page": index, "mode": "ocr", "chars": len(ocr_text)})

    return {"text": "\n\n".join(texts).strip(), "meta": {"file_type": "pdf", "pages": page_stats}}


def extract_text_from_image(image_path: Path) -> dict:
    image = Image.open(image_path)
    text = run_tesseract(image)
    return {
        "text": text,
        "meta": {"file_type": "image", "pages": [{"page": 1, "mode": "ocr", "chars": len(text)}]},
    }


def extract_text_from_file(file_path: str) -> dict:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        return extract_text_from_image(path)

    raise ValueError(f"Unsupported file type: {suffix}")


def run_tesseract(image: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(image, lang="eng+jpn").strip()
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract executable was not found. Install Tesseract OCR and add it to PATH."
        ) from exc
