from fastapi import APIRouter
from pydantic import BaseModel
import json

from state import app_state
from services.kit_reader import get_scene_by_uuid, get_scenes_around
from prompts.global_prompt import GLOBAL_PROMPT
from prompts.dialogue_prompt import DIALOGUE_PROMPT

router = APIRouter()

class DialogueRequest(BaseModel):
    scene_uuid: str
    user_message: str

@router.post("/api/dialogue/generate")
def generate_dialogue(req: DialogueRequest):
    project_data = app_state.get("project_data")
    memory = app_state.get("memory_data") or {}
    gemini = app_state.get("gemini")
    writer = app_state.get("writer")
    
    if not project_data:
        return {"success": False, "error": "Project not loaded"}
        
    scenes = project_data.get("scenes", [])
    raw_xml = project_data.get("raw_xml", "")
    
    scene = get_scene_by_uuid(raw_xml, req.scene_uuid)
    if not scene:
        return {"success": False, "error": "Scene not found"}
        
    around = get_scenes_around(scenes, req.scene_uuid, count=1)
    prev_scenes = around.get("prev", [])
    next_scenes = around.get("next", [])
    
    synopsis = memory.get("synopsis", "")
    chars = memory.get("characters", [])
    chars_text = json.dumps(chars, ensure_ascii=False, indent=2)
    
    context_parts = [
        f"СИНОПСИС:\n{synopsis}",
        f"ПЕРСОНАЖИ:\n{chars_text}",
    ]
    
    if prev_scenes:
        context_parts.append("ПРЕДЫДУЩАЯ СЦЕНА:\n" + prev_scenes[-1].get("heading", ""))
        
    current_scene_info = f"Заголовок: {scene.get('heading', '')}\nУчастники: {', '.join(scene.get('participants', []))}\nДействие: {scene.get('action_text', '')}"
    context_parts.append(f"ТЕКУЩАЯ СЦЕНА (для диалога):\n{current_scene_info}")
    
    if next_scenes:
        context_parts.append("СЛЕДУЮЩАЯ СЦЕНА:\n" + next_scenes[0].get("heading", ""))
        
    context = "\n\n".join(context_parts)
    prompt = GLOBAL_PROMPT + "\n\n" + DIALOGUE_PROMPT
    
    try:
        result_text = gemini.generate(prompt, req.user_message, context)
        new_xml = writer.xml_to_kitsp_format(result_text)
        updated_xml = writer.save_scene(raw_xml, req.scene_uuid, new_xml)
        
        app_state["project_data"]["raw_xml"] = updated_xml
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
