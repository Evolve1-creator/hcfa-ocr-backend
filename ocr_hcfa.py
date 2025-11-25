import io
import re
from typing import List

import fitz  # PyMuPDF
from PIL import Image
import pytesseract

from models import Claim, ClaimLine

# Simple regex patterns
CPT_REGEX = re.compile(r"\b(\d{5})\b")
ICD10_REGEX = re.compile(
    r"\b([A-TV-Z][0-9A-TV-Z][0-9A-TV-Z](?:\.[0-9A-TV-Z]{1,4})?)\b"
)
DOB_REGEX = re.compile(
    r"\b(0[1-9]|1[0-2])[\/\-](0[1-9]|[12][0-9]|3[01])[\/\-](19|20)\d{2}\b"
)


def _pdf_to_image(file_bytes: bytes) -> Image.Image:
    """Render the first page of a PDF into a PIL Image using PyMuPDF.

    This avoids external poppler/ghostscript dependencies and works well on Railway.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    if doc.page_count == 0:
        raise ValueError("PDF has no pages.")
    page = doc.load_page(0)
    # Render at 200 dpi equivalent for decent OCR quality
    pix = page.get_pixmap(dpi=200)
    mode = "RGB"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    return img


def _bytes_to_image(file_bytes: bytes, filename: str) -> Image.Image:
    """Convert uploaded bytes into a single PIL.Image.

    - If a PDF: render first page using PyMuPDF.
    - Otherwise: attempt to open as an image file (JPG/PNG/TIFF, etc.).
    """
    lower_name = (filename or "").lower()
    if lower_name.endswith(".pdf"):
        return _pdf_to_image(file_bytes)

    # Fallback: treat as image
    img = Image.open(io.BytesIO(file_bytes))
    return img.convert("RGB")


def _run_ocr(img: Image.Image) -> str:
    """Run Tesseract OCR on a PIL image and return the full extracted text."""
    config = "--psm 6"
    text = pytesseract.image_to_string(img, config=config)
    return text


def parse_hcfa_file(file_bytes: bytes, filename: str) -> Claim:
    """Parse a HCFA form from PDF or image bytes into a Claim model.

    This is intentionally conservative and educational:
    - Attempts to detect CPT codes, ICD-10 codes, and DOB.
    - Builds one ClaimLine per CPT.
    - Maps ICD codes to pointers A, B, C, ...
    """
    if not file_bytes:
        raise ValueError("Empty file bytes.")

    img = _bytes_to_image(file_bytes, filename)
    full_text = _run_ocr(img)

    # Extract CPT codes in the order they appear, de-duplicated
    cpt_codes: List[str] = []
    for match in CPT_REGEX.finditer(full_text):
        code = match.group(1)
        if code not in cpt_codes:
            cpt_codes.append(code)

    # Extract ICD-10 codes
    icd_codes: List[str] = []
    for match in ICD10_REGEX.finditer(full_text):
        code = match.group(1)
        if len(code) >= 3 and code not in icd_codes:
            icd_codes.append(code)

    # Extract DOB (first match)
    dob_match = DOB_REGEX.search(full_text)
    dob = dob_match.group(0) if dob_match else None

    # Build claim lines
    lines: List[ClaimLine] = []
    if cpt_codes:
        default_pointer = "A" if icd_codes else ""
        for idx, cpt in enumerate(cpt_codes, start=1):
            diagnosis_pointers = [default_pointer] if default_pointer else []
            lines.append(
                ClaimLine(
                    line_number=idx,
                    cpt=cpt,
                    modifiers=[],
                    diagnosis_pointers=diagnosis_pointers,
                    units=1,
                    charges=0.0,
                )
            )

    # Map ICD codes to letters A, B, C, ...
    icd_map = {chr(65 + i): code for i, code in enumerate(icd_codes)}

    claim = Claim(
        payer="",
        pos="",
        lines=lines,
        icd10=icd_map,
        patient_dob=dob,
    )
    return claim
