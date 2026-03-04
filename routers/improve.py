from fastapi import APIRouter
from pydantic import BaseModel
import json

from state import app_state
from services.kit_reader import get_scene_by_uuid
from prompts.global_prompt import GLOBAL_PROMPT
from prompts.improve_prompt import IMPROVE_PROMPT

router = APIRouter()

class ImproveRequest(BaseModel):
    scene_uuid: str
    user_message: str

@router.post("/api/improve/generate")
def improve_scene(req: ImproveRequest):
    project_data = app_state.get("project_data")
    memory = app_state.get("memory_data") or {}
    gemini = app_state.get("gemini")
    writer = app_state.get("writer")
    
    if not project_data:
        return {"success": False, "error": "Project not loaded"}
        
    raw_xml = project_data.get("raw_xml", "")
    scene = get_scene_by_uuid(raw_xml, req.scene_uuid)
    
    if not scene:
        return {"success": False, "error": "Scene not found"}
        
    synopsis = memory.get("synopsis", "")
    chars = memory.get("characters", [])
    chars_text = json.dumps(chars, ensure_ascii=False, indent=2)
    
    full_scene_xml = scene.get("full_xml", "")
    
    context = f"СИНОПСИС:\n{synopsis}\n\nПЕРСОНАЖИ:\n{chars_text}"
    prompt = GLOBAL_PROMPT + "\n\n" + IMPROVE_PROMPT
    
    user_msg_formatted = f"Пожелание: {req.user_message}\nСцена:\n{full_scene_xml}"
    
    try:
        result_text = gemini.generate(prompt, user_msg_formatted, context)
        new_xml = writer.xml_to_kitsp_format(result_text)
        updated_xml = writer.save_scene(raw_xml, req.scene_uuid, new_xml)
        
        app_state["project_data"]["raw_xml"] = updated_xml
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
