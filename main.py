from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from ocr_hcfa import parse_hcfa_file
from rules_engine import run_all_checks
from models import Claim, AuditResult

app = FastAPI(title="HCFA OCR + Audit Backend")

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ocr-hcfa", response_model=Claim)
async def ocr_hcfa(file: UploadFile = File(...)):
    data = await file.read()
    return parse_hcfa_file(data, file.filename)

@app.post("/analyze-claim", response_model=AuditResult)
async def analyze_claim(claim: Claim):
    return run_all_checks(claim)
