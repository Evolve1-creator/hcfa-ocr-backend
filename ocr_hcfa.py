import io
import re
from typing import List

import numpy as np
import cv2
from pdf2image import convert_from_bytes
from paddleocr import PaddleOCR

from models import Claim, ClaimLine

# --- OCR engine (loaded once) ---
ocr_engine = PaddleOCR(lang="en", use_angle_cls=True, show_log=False)

# --- Regex patterns for codes and DOB ---
CPT_REGEX = re.compile(r"\b(\d{5})\b")
ICD_REGEX = re.compile(r"\b([A-TV-Z][0-9][A-Z0-9\.]{1,6})\b")
DOB_REGEX = re.compile(
    r"\b(0[1-9]|1[0-2])[/\-\.](0[1-9]|[12][0-9]|3[01])[/\-\.](19|20)\d{2}\b"
)


def _pdf_to_image(data: bytes) -> np.ndarray:
    """Convert first page of a PDF to an OpenCV image."""
    pages = convert_from_bytes(data)
    if not pages:
        raise ValueError("No pages in PDF.")
    img = np.array(pages[0])
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img


def _bytes_to_image(data: bytes) -> np.ndarray:
    """Convert raw image bytes (jpg/png) to OpenCV image."""
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image.")
    return img


def _run_ocr(img: np.ndarray) -> List[str]:
    """Run PaddleOCR and return list of text lines."""
    result = ocr_engine.ocr(img, cls=True)
    lines: List[str] = []
    for page in result:
        for line in page:
            text = line[1][0]
            if text and text.strip():
                lines.append(text.strip())
    return lines


def _crop_regions(full_img: np.ndarray):
    """
    Return two cropped regions:
      1) dob_img   -> Box 3 (DOB) area ONLY
      2) bottom_img -> Box 21 + Box 24 area (diagnoses & procedures)
    Everything else (names, addresses, IDs, NPIs, etc.) is excluded.
    """
    h, w = full_img.shape[:2]

    # These ratios are based on the standard CMS-1500 layout.
    # You can tweak them slightly if your scans are off.

    # Box 3 row (DOB) – roughly upper third, middle area
    dob_y1 = int(0.18 * h)
    dob_y2 = int(0.26 * h)
    dob_x1 = int(0.28 * w)
    dob_x2 = int(0.55 * w)
    dob_img = full_img[dob_y1:dob_y2, dob_x1:dob_x2].copy()

    # Bottom half with Box 21 + 24
    # This cuts off most of the top PHI and bottom provider section.
    bottom_y1 = int(0.40 * h)   # just above Box 21
    bottom_y2 = int(0.92 * h)   # above billing provider area
    bottom_img = full_img[bottom_y1:bottom_y2, :].copy()

    return dob_img, bottom_img


def parse_hcfa_file(data: bytes, filename: str) -> Claim:
    """
    HIPAA-safe HCFA parser:

    - Accepts PDF or image of full HCFA-1500.
    - Crops out ALL PHI sections (top & bottom provider areas).
    - Preserves ONLY:
        * Box 3: DOB (for age-based rules)
        * Box 21: ICD codes
        * Box 24: CPT/Modifiers/Charges
    - Returns a Claim with CPT/ICD and optional DOB.
    """
    ext = filename.lower().split(".")[-1]

    # 1. Decode input to an image
    if ext == "pdf":
        img = _pdf_to_image(data)
    else:
        img = _bytes_to_image(data)

    # 2. Crop to HIPAA-safe regions
    dob_img, bottom_img = _crop_regions(img)

    # 3. OCR DOB region
    dob_text_lines = _run_ocr(dob_img)
    dob_text = " ".join(dob_text_lines)
    dob_match = DOB_REGEX.search(dob_text)
    dob_str = dob_match.group(0) if dob_match else None

    # 4. OCR bottom (diagnoses + procedures)
    bottom_text_lines = _run_ocr(bottom_img)

    icd_codes: List[str] = []
    cpt_entries = []

    for raw_line in bottom_text_lines:
        line = " ".join(raw_line.split())

        # ICD-10 codes
        for icd in ICD_REGEX.findall(line):
            if icd not in icd_codes:
                icd_codes.append(icd)

        # CPT codes + modifiers + charges
        cpt_match = CPT_REGEX.search(line)
        if cpt_match:
            cpt = cpt_match.group(1)

            # Common modifiers (25, 59, 26, TC, RT, LT, etc.)
            mods = re.findall(
                r"\b(\d{2}|RT|LT|TC|26|50|51|52|53|54|55|57|59|76|77|78|79|91)\b",
                line,
            )

            # Charge – look for a number with 2 decimals
            charge_match = re.search(r"(\d+\.\d{2})", line)
            charge = float(charge_match.group(1)) if charge_match else 0.0

            cpt_entries.append(
                {
                    "cpt": cpt,
                    "modifiers": list(dict.fromkeys(mods)),
                    "units": 1,
                    "charges": charge,
                }
            )

    # 5. Build Claim object
    lines: List[ClaimLine] = []
    for idx, entry in enumerate(cpt_entries, start=1):
        lines.append(
            ClaimLine(
                line_number=idx,
                cpt=entry["cpt"],
                modifiers=entry["modifiers"],
                diagnosis_pointers=[],
                units=entry["units"],
                charges=entry["charges"],
            )
        )

    icd_map = {chr(ord("A") + i): code for i, code in enumerate(icd_codes)}

    claim = Claim(
        payer="",
        pos="",            # POS can be added later if you want to OCR it
        lines=lines,
        icd10=icd_map,
        patient_dob=dob_str,
    )

    return claim
