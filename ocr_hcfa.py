import re
from models import Claim, ClaimLine

CPT_REGEX = re.compile(r"\b\d{5}\b")
ICD_REGEX = re.compile(r"[A-TV-Z][0-9][A-Z0-9\.]{1,6}")

def parse_hcfa_file(data, filename):
    text = ""
    try:
        text = data.decode(errors="ignore")
    except:
        text = ""

    cpts = CPT_REGEX.findall(text)
    icds = ICD_REGEX.findall(text)

    lines = []
    for i, c in enumerate(cpts, 1):
        lines.append(ClaimLine(
            line_number=i,
            cpt=c,
            modifiers=[],
            diagnosis_pointers=[],
            units=1,
            charges=0.0
        ))

    icd_map = {chr(65+i): code for i, code in enumerate(icds)}

    return Claim(
        payer="",
        pos="11",
        lines=lines,
        icd10=icd_map
    )
