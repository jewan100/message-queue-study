from fastapi import APIRouter

from ocr_engine.schemas import PredictRequest, PredictResponse
from ocr_engine.predictor import run_ocr

router = APIRouter()

@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    return run_ocr(req)
