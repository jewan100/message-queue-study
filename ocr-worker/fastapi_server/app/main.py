from contextlib import asynccontextmanager

from fastapi import FastAPI

from .routes import ocr_router
from ocr_engine.model_loader import get_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = get_pipeline()
    yield
    
    return

def create_app() -> FastAPI:
  app = FastAPI(
    title="OCR Service", 
    version="1.0.0",
    lifespan=lifespan,
  )
  
  app.include_router(ocr_router, tags=["OCR"])
  
  return app

app = create_app()