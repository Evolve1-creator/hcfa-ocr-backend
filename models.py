from pydantic import BaseModel
from typing import List, Dict, Optional


class ClaimLine(BaseModel):
    line_number: int
    cpt: str
    modifiers: List[str] = []
    diagnosis_pointers: List[str] = []
    units: int = 1
    charges: float = 0.0


class Claim(BaseModel):
    payer: str = ""
    pos: str = ""
    lines: List[ClaimLine]
    icd10: Dict[str, str] = {}
    patient_dob: Optional[str] = None
