# ocr_engine/pipeline.py
from __future__ import annotations

from pathlib import Path
import threading
from typing import Any


__all__ = ["OCRPipelines"]


class OCRPipelines:
    """
    PaddleOCR 의 FormulaRecognitionPipeline 을 감싸는 래퍼 클래스.

    - 초기화 시 수식 인식 모델/레이아웃 모델의 디렉터리와 이름, 디바이스를 전달받아
      FormulaRecognitionPipeline 인스턴스를 생성한다.
    - predict() 메서드에서는 내부적으로 Lock 을 사용하여 thread-safe 하게
      model.predict() 를 호출한다.
    """

    def __init__(
        self,
        formula_model_name: str,
        formula_model_dir: str | Path,
        layout_model_name: str,
        layout_model_dir: str | Path,
        device: str = "cpu",
        use_doc_orientation_classify: bool = False,
        use_doc_unwarping: bool = False,
    ) -> None:
        try:
            from paddleocr import FormulaRecognitionPipeline
        except Exception as e:
            raise RuntimeError(
                "Failed to import paddleocr.FormulaRecognitionPipeline."
            ) from e

        fdir = Path(formula_model_dir).expanduser()
        ldir = Path(layout_model_dir).expanduser()
        if not fdir.exists():
            raise FileNotFoundError(f"Model directory not found: {fdir}")
        if not ldir.exists():
            raise FileNotFoundError(f"Model directory not found: {ldir}")

        # 멀티 스레드 환경에서 model.predict() 호출을 보호하기 위한 Lock
        self._lock = threading.Lock()

        self.model = FormulaRecognitionPipeline(
            formula_recognition_model_name=str(formula_model_name),
            formula_recognition_model_dir=str(fdir),
            layout_detection_model_name=str(layout_model_name),
            layout_detection_model_dir=str(ldir),
            use_doc_orientation_classify=use_doc_orientation_classify,
            use_doc_unwarping=use_doc_unwarping,
            device=device,
        )

    def predict(self, input_path: str, batch_size: int = 1) -> Any:
        with self._lock:
            return self.model.predict(input=input_path, batch_size=batch_size)
