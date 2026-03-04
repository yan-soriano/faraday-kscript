from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from state import app_state
from services.validator import validate_structure, format_errors_for_ai
from prompts.global_prompt import GLOBAL_PROMPT
from prompts.outline_prompt import OUTLINE_STRUCTURE_PROMPT, OUTLINE_DESCRIPTIONS_PROMPT

router = APIRouter()

class OutlineRequest(BaseModel):
    user_message: str

def split_scenes_text(text: str) -> list:
    scenes = []
    current_scene = []
    for line in text.split('\n'):
        l_upper = line.strip().upper()
        if l_upper.startswith("ИНТ.") or l_upper.startswith("ЭКСТ.") or l_upper.startswith("НАТ."):
            if current_scene and any(c.strip() for c in current_scene):
                scenes.append("\n".join(current_scene).strip())
            current_scene = [line]
        else:
            current_scene.append(line)
    if current_scene and any(c.strip() for c in current_scene):
        scenes.append("\n".join(current_scene).strip())
    return scenes

def parse_structure(text: str) -> list:
    scenes = []
    raw_scenes = split_scenes_text(text)
    for idx, scene_text in enumerate(raw_scenes):
        lines = [l.strip() for l in scene_text.split('\n') if l.strip()]
        if not lines: continue
        heading = lines[0]
        participants = []
        if len(lines) > 1:
            participants = [p.strip().upper() for p in lines[1].split(',') if p.strip()]
        scenes.append({
            "index": idx + 1,
            "heading": heading,
            "participants": participants
        })
    return scenes

@router.post("/api/outline/generate")
def generate_outline(req: OutlineRequest):
    def sse_generator():
        try:
            gemini = app_state.get("gemini")
            writer = app_state.get("writer")
            
            if not gemini or not writer:
                yield f"data: {json.dumps({'step': 'error', 'message': 'Жоба жүктелмеген немесе API кілті қосылмаған!'}, ensure_ascii=False)}\n\n"
                return
                
            memory = app_state.get("memory_data") or {}
            
            synopsis = memory.get("synopsis", "")
            chars = memory.get("characters", [])
            chars_text = json.dumps(chars, ensure_ascii=False, indent=2)
            
            context = f"СИНОПСИС:\n{synopsis}\n\nПЕРСОНАЖИ И ЛИМИТЫ:\n{chars_text}"
            
            yield f"data: {json.dumps({'step': 'generating_structure', 'message': 'Структура жасалуда...'}, ensure_ascii=False)}\n\n"
            
            prompt_struct = OUTLINE_STRUCTURE_PROMPT + "\n\n" + GLOBAL_PROMPT
            structure_text = gemini.generate(prompt_struct, req.user_message, context)
            
            parsed = parse_structure(structure_text)
            
            yield f"data: {json.dumps({'step': 'validating', 'message': 'Лимиттер тексерілуде...'}, ensure_ascii=False)}\n\n"
            errors = validate_structure(parsed, chars)
            
            attempts = 0
            while errors and attempts < 3:
                attempts += 1
                yield f"data: {json.dumps({'step': 'fixing', 'message': f'Қателер түзетілуде (попытка {attempts}/3)...'}, ensure_ascii=False)}\n\n"
                
                error_report = format_errors_for_ai(errors)
                fix_msg = f"ПРЕДЫДУЩАЯ СТРУКТУРА:\n{structure_text}\n\nОШИБКИ:\n{error_report}\n\nИсправь указанные ошибки, не меняй остальные сцены."
                
                structure_text = gemini.generate(prompt_struct, fix_msg, context)
                parsed = parse_structure(structure_text)
                errors = validate_structure(parsed, chars)
                
            yield f"data: {json.dumps({'step': 'generating_descriptions', 'message': 'Сипаттамалар жазылуда...'}, ensure_ascii=False)}\n\n"
            
            prompt_desc = OUTLINE_DESCRIPTIONS_PROMPT + "\n\n" + GLOBAL_PROMPT
            desc_text = gemini.generate(prompt_desc, "Добавь описания к проверенной структуре ниже:\n\n" + structure_text, context)
            
            yield f"data: {json.dumps({'step': 'converting', 'message': 'XML-ге айналдырылуда...'}, ensure_ascii=False)}\n\n"
            scene_blocks = split_scenes_text(desc_text)
            xml_parts = []
            for b in scene_blocks:
                part = writer.xml_to_kitsp_format(b)
                if part:
                    xml_parts.append(part)
                    
            full_xml = "<?xml version=\"1.0\"?>\n<scenario version=\"1.0\">\n" + "\n".join(xml_parts) + "\n</scenario>\n"
            
            writer.save_full_scenario(full_xml)
            yield f"data: {json.dumps({'step': 'done', 'message': 'Дайын! KIT Scenarist-те жобаны қайта ашыңыз.'}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'step': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")
