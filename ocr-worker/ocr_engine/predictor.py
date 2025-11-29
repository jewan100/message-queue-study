# ocr_engine/predictor.py
from pathlib import Path

from .config import DATA_DIR
from .model_loader import get_pipeline
from .schemas import PredictRequest, PredictResponse


def run_ocr(req: PredictRequest) -> PredictResponse:
   
    pipelines = get_pipeline()

    pdf_path: Path = DATA_DIR / req.pdf_name
    if not pdf_path.is_file():
        return PredictResponse(
            message=f"pdf not found: {pdf_path}"
        )

    _ = pipelines.predict(input_path=str(pdf_path), batch_size=1)

    return PredictResponse(
        message="ok"
    )
