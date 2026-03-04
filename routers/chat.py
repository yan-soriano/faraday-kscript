from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import json

from state import app_state
from services.kit_reader import search_scenes_by_keywords
from prompts.global_prompt import GLOBAL_PROMPT
from prompts.chat_prompt import CHAT_PROMPT

router = APIRouter()

class ChatMessageRequest(BaseModel):
    message: str
    history: List[Dict[str, str]]

class ChatInsertRequest(BaseModel):
    scene_uuid: str
    content: str

@router.post("/api/chat/message")
def chat_message(req: ChatMessageRequest):
    def sse_generator():
        try:
            project_data = app_state.get("project_data")
            memory = app_state.get("memory_data") or {}
            gemini = app_state.get("gemini")
            
            scenes = project_data.get("scenes", []) if project_data else []
            
            relevant_scenes = search_scenes_by_keywords(scenes, req.message)
            
            synopsis = memory.get("synopsis", "")
            chars = memory.get("characters", [])
            chars_text = json.dumps(chars, ensure_ascii=False, indent=2)
            
            scenes_context = ""
            for i, s in enumerate(relevant_scenes):
                scenes_context += f"СЦЕНА {i+1} ({s['heading']}):\n{s.get('action_text', '')}\n\n"
                
            context = f"СИНОПСИС:\n{synopsis}\n\nПЕРСОНАЖИ:\n{chars_text}\n\nНАЙДЕННЫЕ СЦЕНЫ:\n{scenes_context}"
            prompt = GLOBAL_PROMPT + "\n\n" + CHAT_PROMPT
            
            formatted_history = ""
            for msg in req.history:
                role = "Пользователь" if msg.get("role") == "user" else "Ассистент"
                formatted_history += f"{role}: {msg.get('text', '')}\n"
                
            full_message = req.message
            if formatted_history:
                full_message = f"ИСТОРИЯ ЧАТА:\n{formatted_history}\n\nНОВОЕ СООБЩЕНИЕ ИЛИ ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{req.message}"
                
            stream = gemini.generate_stream(prompt, full_message, context)
            
            for chunk in stream:
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@router.post("/api/chat/insert")
def chat_insert(req: ChatInsertRequest):
    project_data = app_state.get("project_data")
    writer = app_state.get("writer")
    
    if not project_data or not writer:
        return {"success": False, "error": "Project not loaded"}
        
    try:
        raw_xml = project_data.get("raw_xml", "")
        new_xml = writer.xml_to_kitsp_format(req.content)
        updated_xml = writer.save_scene(raw_xml, req.scene_uuid, new_xml)
        
        app_state["project_data"]["raw_xml"] = updated_xml
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
