import io
import re
from typing import List

from PIL import Image
from paddleocr import PaddleOCR

from models import Claim, ClaimLine

# Initialize OCR once
ocr_engine = PaddleOCR(lang="en", use_angle_cls=True, show_log=False)

CPT_REGEX = re.compile(r"\b(\d{5})\b")
ICD_REGEX = re.compile(r"\b([A-TV-Z][0-9][A-Z0-9\.]{1,6})\b")
DOB_REGEX = re.compile(
    r"\b(0[1-9]|1[0-2])[/\-\.](0[1-9]|[12][0-9]|3[01])[/\-\.](19|20)\d{2}\b"
)

def _load_image_from_bytes(data: bytes, filename: str) -> Image.Image:
    """
    Load an image from bytes. For now we support ONLY image types
    (jpg, jpeg, png). PDFs are not supported yet on Railway.
    """
    ext = filename.lower().split(".")[-1]
    if ext in {"jpg", "jpeg", "png"}:
        return Image.open(io.BytesIO(data)).convert("RGB")
    # You can add PDF support later if you install poppler on your host.
    raise ValueError("Please upload a JPG or PNG image of the HCFA form.")

def _crop_regions(img: Image.Image):
    """
    Returns:
      dob_img      -> region around Box 3 (DOB)
      bottom_img   -> region around Box 21 + 24 (ICD + CPT lines)

    The ratios are based on a standard CMS-1500 layout. You can tune
    them later if your scanner crops differently.
    """
    w, h = img.size

    # Box 3 (DOB) region
    dob_y1 = int(0.18 * h)
    dob_y2 = int(0.26 * h)
    dob_x1 = int(0.28 * w)
    dob_x2 = int(0.55 * w)
    dob_img = img.crop((dob_x1, dob_y1, dob_x2, dob_y2))

    # Bottom portion with Box 21 + 24
    bottom_y1 = int(0.40 * h)
    bottom_y2 = int(0.92 * h)
    bottom_img = img.crop((0, bottom_y1, w, bottom_y2))

    return dob_img, bottom_img

def _run_ocr_pil(pil_img: Image.Image) -> List[str]:
    """
    Run PaddleOCR on a PIL image and return text lines.
    """
    import numpy as np

    np_img = np.array(pil_img)
    results = ocr_engine.ocr(np_img, cls=True)

    lines: List[str] = []
    for page in results:
        for line in page:
            text = line[1][0]
            if text:
                lines.append(text.strip())
    return lines

def parse_hcfa_file(data: bytes, filename: str) -> Claim:
    """
    HIPAA-safe HCFA parser:

    - Accepts a JPG/PNG of the full HCFA-1500.
    - Crops away the PHI-heavy sections (names, addresses, IDs).
    - Keeps:
        * Box 3 DOB (for age-dependent rules)
        * Box 21 ICD codes
        * Box 24 CPT/modifiers/charges

    Returns a Claim object with lines + ICD map + optional DOB.
    """
    # 1) Load & crop
    img = _load_image_from_bytes(data, filename)
    dob_img, bottom_img = _crop_regions(img)

    # 2) OCR DOB region
    dob_lines = _run_ocr_pil(dob_img)
    dob_text = " ".join(dob_lines)
    dob_match = DOB_REGEX.search(dob_text)
    dob = dob_match.group(0) if dob_match else None

    # 3) OCR bottom (diagnosis + procedures)
    bottom_lines = _run_ocr_pil(bottom_img)

    icd_codes: List[str] = []
    cpt_entries = []

    for raw in bottom_lines:
        line = raw.strip()

        # ICD-10 codes
        for icd in ICD_REGEX.findall(line):
            if icd not in icd_codes:
                icd_codes.append(icd)

        # CPT codes + modifiers + charges
        cpt_match = CPT_REGEX.search(line)
        if cpt_match:
            cpt = cpt_match.group(1)

            mods = re.findall(
                r"\b(\d{2}|RT|LT|TC|26|50|51|52|53|57|59|76|77)\b",
                line,
            )

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

    # 4) Build Claim object
    lines: List[ClaimLine] = []
    for idx, item in enumerate(cpt_entries, 1):
        lines.append(
            ClaimLine(
                line_number=idx,
                cpt=item["cpt"],
                modifiers=item["modifiers"],
                diagnosis_pointers=[],
                units=item["units"],
                charges=item["charges"],
            )
        )

    icd_map = {chr(65 + i): code for i, code in enumerate(icd_codes)}

    return Claim(
        payer="",
        pos="",
        lines=lines,
        icd10=icd_map,
        patient_dob=dob,
    )
