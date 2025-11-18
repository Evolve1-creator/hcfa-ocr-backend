# HCFA OCR Backend (Railway)

This is a minimal FastAPI service used by your Coding Companion app
to OCR HCFA-1500 images and return de-identified claim data.

## Endpoints

- `GET /` – health check
- `POST /audit` – upload a JPG/PNG HCFA image, receive parsed claim JSON
- `POST /ocr-hcfa` – same as `/audit` (alias for older frontend code)

## Deployment notes

- Designed for Railway on Python 3.10
- Uses PaddleOCR + Pillow only (no OpenCV / libGL)
- Currently supports JPG/PNG images, not PDFs
