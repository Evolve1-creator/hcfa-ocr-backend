import io
import re
from typing import List

import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
from pdf2image import convert_from_bytes

from models import Claim, ClaimLine

# Initialize OCR engine once at import time
ocr_engine = PaddleOCR(lang="en", use_angle_cls=True, show_log=False)

# Simple regex patterns
CPT_REGEX = re.compile(r"\b(\d{5})\b")
ICD10_REGEX = re.compile(
    r"\b([A-TV-Z][0-9A-TV-Z][0-9A-TV-Z](?:\.[0-9A-TV-Z]{1,4})?)\b"
)
DOB_REGEX = re.compile(
    r"\b(0[1-9]|1[0-2])[\/\-](0[1-9]|[12][0-9]|3[01])[\/\-](19|20)\d{2}\b"
)


def _bytes_to_image(file_bytes: bytes, filename: str) -> Image.Image:
    """Convert uploaded bytes into a single PIL.Image.

    - If a PDF: convert first page to image.
    - Otherwise: attempt to open as an image file.
    """
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        pages = convert_from_bytes(file_bytes, dpi=200)
        if not pages:
            raise ValueError("No pages found in PDF.")
        return pages[0].convert("RGB")

    # Fallback: treat as image
    img = Image.open(io.BytesIO(file_bytes))
    return img.convert("RGB")


def _run_ocr(img: Image.Image) -> List[str]:
    """Run PaddleOCR on a PIL image and return a list of recognized text strings."""
    np_img = np.array(img)
    result = ocr_engine.ocr(np_img, cls=True)
    texts: List[str] = []
    for line in result:
        # Each line is a list of [box, (text, confidence)]
        for box in line:
            if len(box) >= 2 and isinstance(box[1], (list, tuple)) and len(box[1]) >= 1:
                text = box[1][0]
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
    return texts


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
    texts = _run_ocr(img)

    # Combine text into a single string for regex scanning
    full_text = "\n".join(texts)

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
        # Basic sanity filter: avoid things that are clearly not ICD
        if len(code) >= 3 and code not in icd_codes:
            icd_codes.append(code)

    # Extract DOB (first match)
    dob_match = DOB_REGEX.search(full_text)
    dob = dob_match.group(0) if dob_match else None

    # Build claim lines
    lines: List[ClaimLine] = []
    if not cpt_codes:
        # Still return a Claim object, but with no lines
        pass
    else:
        # Default diagnosis pointers – if we have ICDs, point to "A" by default
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
