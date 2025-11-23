# ocr_engine/config.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data" / "pdfs"
MODEL_ROOT = BASE_DIR / "models"

FORMULA_MODEL_DIR = MODEL_ROOT / "PP-FormulaNet_plus-L_infer"
LAYOUT_MODEL_DIR = MODEL_ROOT / "PP-DocLayout_plus-L_infer"

FORMULA_MODEL_NAME = "PP-FormulaNet_plus-L"
LAYOUT_MODEL_NAME = "PP-DocLayout_plus-L"

DEVICE = "gpu"
