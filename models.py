from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class ClaimLine(BaseModel):
    line_number: int
    cpt: str
    modifiers: List[str] = []
    diagnosis_pointers: List[str] = []
    units: float = 1
    charges: float = 0.0


class Claim(BaseModel):
    # Non-PHI claim data only
    payer: str = ""
    pos: str = ""
    lines: List[ClaimLine]
    icd10: Dict[str, str] = {}

    # Box 3 – patient date of birth (kept for age-based logic)
    # Keep as a plain string like "01/23/1980" for now
    patient_dob: Optional[str] = None


class AuditIssue(BaseModel):
    severity: str
    message: str
    line_numbers: List[int] = []
    code_context: Optional[str] = None


class AuditResult(BaseModel):
    score: int
    issues: List[AuditIssue] = []

