from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ocr_hcfa import parse_hcfa_file

app = FastAPI(title="HCFA OCR Backend")

# Allow calls from your frontend (Vercel domain, localhost, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can restrict this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "ok"}

def _run_parse(data: bytes, filename: str):
    try:
        claim = parse_hcfa_file(data, filename)
        return claim
    except ValueError as e:
        # Bad input (e.g. unsupported file type)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected error
        raise HTTPException(status_code=500, detail="Failed to read claim")

@app.post("/audit")
async def audit(file: UploadFile = File(...)):
    data = await file.read()
    claim = _run_parse(data, file.filename)
    return claim.dict()

# Alias so older frontend code using /ocr-hcfa still works
@app.post("/ocr-hcfa")
async def ocr_hcfa(file: UploadFile = File(...)):
    data = await file.read()
    claim = _run_parse(data, file.filename)
    return claim.dict()
