import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Гарантируем, что папка frontend существует, чтобы FastAPI не выбросил ошибку при старте
os.makedirs("frontend", exist_ok=True)

from state import app_state

# Импортируем роутеры после определения app_state, так как они ссылаются на него
from routers import outline, dialogue, improve, chat, memory_router
from services.kit_reader import load_project
from services.kit_writer import KitWriter
from services.memory import load_memory, save_memory
from services.gemini import GeminiClient

app = FastAPI(title="ИИ-ассистент сценариста")

# Подключаем роутеры
app.include_router(outline.router)
app.include_router(dialogue.router)
app.include_router(improve.router)
app.include_router(chat.router)
app.include_router(memory_router.router)

CONFIG_PATH = "config.json"

import os
from dotenv import load_dotenv

load_dotenv()

@app.on_event("startup")
def startup_event():
    # Загружаем настройки и инициализируем Gemini при старте
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        app_state["gemini"] = GeminiClient(api_key=api_key, model="gemini-2.5-pro")
    else:
        print("ВНИМАНИЕ: Переменная среды GEMINI_API_KEY не найдена.")

class ProjectLoadRequest(BaseModel):
    path: str

@app.post("/api/project/load")
def load_project_api(req: ProjectLoadRequest):
    try:
        # Загружаем данные
        project_data = load_project(req.path)
        memory_data = load_memory(req.path)
        writer = KitWriter(req.path)
        
        # Сохраняем в глобальное состояние (app_state)
        app_state["kitsp_path"] = req.path
        app_state["project_data"] = project_data
        app_state["memory_data"] = memory_data
        app_state["writer"] = writer
        
        return {
            "scenes": project_data.get("scenes", []),
            "project_name": project_data.get("project_name", ""),
            "has_memory": memory_data is not None
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class MemorySaveRequest(BaseModel):
    synopsis: str
    characters: list

@app.post("/api/memory/save")
def save_memory_api(req: MemorySaveRequest):
    if not app_state["kitsp_path"]:
        raise HTTPException(status_code=400, detail="Проект не загружен")
        
    data = {"synopsis": req.synopsis, "characters": req.characters}
    
    # Сохраняем существующее время создания, если оно было
    if app_state["memory_data"] and "created_at" in app_state["memory_data"]:
        data["created_at"] = app_state["memory_data"]["created_at"]
        
    try:
        save_memory(app_state["kitsp_path"], data)
        # Перечитываем файл для получения обновленных дат
        app_state["memory_data"] = load_memory(app_state["kitsp_path"])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/memory/load")
def load_memory_api():
    if app_state["memory_data"] is None:
        return {"error": "Память не найдена"}
    return app_state["memory_data"]

@app.post("/api/undo")
def undo_api():
    writer = app_state["writer"]
    if not writer:
        return {"success": False, "error": "Проект не загружен"}
        
    try:
        success = writer.undo()
        if success:
            # Обновляем кэш проекта после отката изменений
            app_state["project_data"] = load_project(app_state["kitsp_path"])
            return {"success": True}
        else:
            return {"success": False, "error": "Нет изменений для отмены"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/config")
def get_config():
    # Возвращаем true, если API ключ загружен в app_state
    has_key = app_state.get("gemini") is not None
    return {"has_api_key": has_key}

# Отдаем фронтенд (последним, чтобы не перебивало API роуты)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
