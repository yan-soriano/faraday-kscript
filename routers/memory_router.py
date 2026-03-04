import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from state import app_state
from services.memory import save_memory, load_memory

router = APIRouter()

class MemoryParseRequest(BaseModel):
    synopsis: str
    characters_raw: str

@router.post("/api/memory/parse-and-save")
def parse_and_save_memory(req: MemoryParseRequest):
    if not app_state.get("kitsp_path"):
        raise HTTPException(status_code=400, detail="Проект не загружен")
        
    gemini = app_state.get("gemini")
    if not gemini:
        raise HTTPException(status_code=400, detail="API кілті не настроен")
        
    prompt = """Распарси список персонажей и верни ТОЛЬКО JSON массив без пояснений.
Каждый персонаж: {"name": "ИМЯ ЗАГЛАВНЫМИ", "age": число, "traits": "характер", "role_type": "main/secondary/adult"}
role_type правила: дети 7-14 лет с главной ролью = "main", остальные дети = "secondary", взрослые = "adult".
Текст: """ + req.characters_raw

    try:
        response_text = gemini.generate(prompt, "", "")
        
        # Очистка возможного мусора от маркдауна (```json)
        json_str = response_text.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        json_str = json_str.strip()
            
        parsed_characters = json.loads(json_str)
        if not isinstance(parsed_characters, list):
            parsed_characters = []
        
        data = {
            "synopsis": req.synopsis,
            "characters": parsed_characters,
            "characters_raw": req.characters_raw
        }
        
        # Сохраняем существующее время создания, если оно было
        if app_state.get("memory_data") and "created_at" in app_state["memory_data"]:
            data["created_at"] = app_state["memory_data"]["created_at"]
            
        save_memory(app_state["kitsp_path"], data)
        # Обновляем память в стейте
        app_state["memory_data"] = load_memory(app_state["kitsp_path"])
        
        return {"success": True, "characters": parsed_characters}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Ошибка парсинга ответа ИИ (JSON). Попробуйте описать понятнее.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
