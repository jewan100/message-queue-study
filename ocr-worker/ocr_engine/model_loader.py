# ocr_engine/model_loader.py
from typing import Optional

from .config import (
    FORMULA_MODEL_NAME,
    FORMULA_MODEL_DIR,
    LAYOUT_MODEL_NAME,
    LAYOUT_MODEL_DIR,
    DEVICE,
)
from .pipeline import OCRPipelines

_pipeline: Optional[OCRPipelines] = None


def _load_pipeline() -> OCRPipelines:
    pipeline = OCRPipelines(
        formula_model_name=FORMULA_MODEL_NAME,
        formula_model_dir=FORMULA_MODEL_DIR,
        layout_model_name=LAYOUT_MODEL_NAME,
        layout_model_dir=LAYOUT_MODEL_DIR,
        device=DEVICE,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
    )
    return pipeline


def get_pipeline() -> OCRPipelines:
    """
    외부에서 호출하는 공개 함수.

    - 전역 캐시에 저장된 OCRPipelines 인스턴스를 반환한다.
    - 아직 생성되지 않았다면 _load_pipeline() 을 호출해 생성 후 캐시에 저장한다.
    """
    global _pipeline

    if _pipeline is None:
        _pipeline = _load_pipeline()

    return _pipeline
