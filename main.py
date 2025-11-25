from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

from models import Claim
from ocr_hcfa import parse_hcfa_file

app = FastAPI(title="HCFA OCR Backend")

# CORS configuration - you can tighten allow_origins to your Vercel domain later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _run_parse(file_bytes: bytes, filename: str) -> Claim:
    """
    Helper to run the OCR/parse logic and normalize errors into HTTPException.
    """
    try:
        claim = parse_hcfa_file(file_bytes, filename)
        return claim
    except HTTPException:
        # Bubble up explicit HTTP exceptions unchanged
        raise
    except Exception as exc:
        # Log to server console for debugging and return a clean 500 to the client
        print("Error parsing HCFA file:", repr(exc))
        raise HTTPException(status_code=500, detail="Error parsing HCFA file")


@app.get("/")
async def root() -> Dict[str, str]:
    return {"status": "ok", "message": "HCFA OCR backend running"}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy"}


@app.post("/ocr-hcfa", response_model=Claim)
async def ocr_hcfa(file: UploadFile = File(...)) -> Claim:
    """
    Primary endpoint the frontend calls when the user uploads a HCFA PDF/image.
    Returns a parsed Claim model as JSON.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = file.filename or ""
    return _run_parse(file_bytes, filename)


@app.post("/analyze-claim")
async def analyze_claim(claim: Claim) -> Dict[str, Any]:
    """
    Simple audit endpoint. Takes a Claim JSON and returns that claim plus a list
    of educational 'issues' or warnings for the user to review.
    """
    issues = []

    if not claim.lines:
        issues.append("No claim lines were detected on the form.")

    # Example basic checks
    for line in claim.lines:
        if not line.cpt:
            issues.append(f"Line {line.line_number}: Missing CPT code.")
        if line.units <= 0:
            issues.append(f"Line {line.line_number}: Units should be at least 1.")
        if line.charges < 0:
            issues.append(f"Line {line.line_number}: Charges cannot be negative.")

    if not claim.icd10:
        issues.append("No ICD-10 diagnosis codes were detected.")
    else:
        # Check if any line has no diagnosis pointers while ICDs exist
        for line in claim.lines:
            if not line.diagnosis_pointers:
                issues.append(
                    f"Line {line.line_number}: No diagnosis pointers linked, even though ICD-10 codes were found."
                )

    if claim.patient_dob is None:
        issues.append("Patient date of birth could not be detected.")

    return {"claim": claim.dict(), "issues": issues}


@app.post("/audit")
async def audit(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Backwards-compatible alias for older frontends that posted a file directly to /audit.
    It runs the same OCR parser and then performs the same simple audit as /analyze-claim.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = file.filename or ""
    claim = _run_parse(file_bytes, filename)

    # Reuse the basic checks from analyze_claim
    issues = []

    if not claim.lines:
        issues.append("No claim lines were detected on the form.")

    for line in claim.lines:
        if not line.cpt:
            issues.append(f"Line {line.line_number}: Missing CPT code.")
        if line.units <= 0:
            issues.append(f"Line {line.line_number}: Units should be at least 1.")
        if line.charges < 0:
            issues.append(f"Line {line.line_number}: Charges cannot be negative.")

    if not claim.icd10:
        issues.append("No ICD-10 diagnosis codes were detected.")
    else:
        for line in claim.lines:
            if not line.diagnosis_pointers:
                issues.append(
                    f"Line {line.line_number}: No diagnosis pointers linked, even though ICD-10 codes were found."
                )

    if claim.patient_dob is None:
        issues.append("Patient date of birth could not be detected.")

    return {"claim": claim.dict(), "issues": issues}
