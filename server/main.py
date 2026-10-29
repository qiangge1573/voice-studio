"""Voice Studio 小程序后端入口。

启动（项目根目录 server/ 下）：
    pip install -r requirements.txt
    ENGINE=mock uvicorn main:app --host 0.0.0.0 --port 8000
或：
    python main.py
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.database import Database
from app.engines import get_engine
from app.routers import auth, batch, dubbing, history, tts, voices
from app.task_manager import TaskManager

settings = Settings()
os.makedirs(settings.samples_dir, exist_ok=True)
os.makedirs(settings.outputs_dir, exist_ok=True)
os.makedirs(settings.videos_dir, exist_ok=True)

app = FastAPI(title="Voice Studio 小程序后端", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.settings = settings
app.state.db = Database(settings.db_path)
app.state.engine = get_engine(settings)
app.state.task_manager = TaskManager()

app.include_router(auth.router)
app.include_router(voices.router)
app.include_router(tts.router)
app.include_router(dubbing.router)
app.include_router(batch.router)
app.include_router(history.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "engine": settings.engine,
        "dev_mode": settings.dev_mode,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
