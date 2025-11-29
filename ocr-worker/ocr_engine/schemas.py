# ocr_engine/schemas.py
from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    pdf_name: str = Field(
        ...,
        description="ocr-worker/data/pdf 디렉터리 아래에 존재하는 PDF 파일 이름",
        examples=["sample.pdf"],
    )


class PredictResponse(BaseModel):
    message: str = Field(..., description="처리 결과 메시지")
