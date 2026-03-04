from __future__ import annotations

def validate_structure(scenes: list, characters: list) -> list:
    """
    Проверяет лимиты участия персонажей в сценах, общего количества сцен и взрослых.
    Возвращает список словарей с ошибками. Если ошибок нет — пустой список.
    """
    errors = []
    
    total_scenes = len(scenes)
    # Проверка общего количества сцен (от 40 до 45)
    if total_scenes < 40 or total_scenes > 45:
        errors.append({
            "type": "wrong_scene_count",
            "character": None,
            "current": total_scenes,
            "limit_min": 40,
            "limit_max": 45,
            "scene_numbers": [],
            "message": f"Общее количество сцен: {total_scenes}, требуется 40-45."
        })
        
    # Проверка на общее количество взрослых персонажей
    adult_count = sum(1 for c in characters if c.get("role_type") == "adult")
    if adult_count > 4:
        errors.append({
            "type": "too_many_adults",
            "character": None,
            "current": adult_count,
            "limit_min": 0,
            "limit_max": 4,
            "scene_numbers": [],
            "message": f"Взрослых персонажей: {adult_count}, максимум 4."
        })
        
    # Подготавливаем учет сцен по персонажам
    char_scenes = {}
    for c in characters:
        name = c.get("name", "").upper()
        char_scenes[name] = []
        
    # Считаем появления
    for scene in scenes:
        scene_idx = scene.get("index", 0)
        for participant in scene.get("participants", []):
            p = participant.upper()
            if p in char_scenes:
                char_scenes[p].append(scene_idx)
                
    # Проверяем лимиты по каждому персонажу
    for char_info in characters:
        name = char_info.get("name", "").upper()
        role = char_info.get("role_type")
        
        participated_scenes = char_scenes.get(name, [])
        count = len(participated_scenes)
        
        limit_min = 0
        limit_max = 9999
        
        if role == "main":
            limit_min = 19
            limit_max = 21
        elif role == "secondary":
            limit_max = 10
        elif role == "adult":
            limit_max = 15
            
        # Проверка "ни в одной сцене"
        if count == 0:
            errors.append({
                "type": "missing_character",
                "character": name,
                "current": 0,
                "limit_min": limit_min,
                "limit_max": limit_max,
                "scene_numbers": [],
                "message": f"{name} не участвует ни в одной сцене."
            })
            continue
            
        # Проверка превышения максимума
        if count > limit_max:
            errors.append({
                "type": "over_limit",
                "character": name,
                "current": count,
                "limit_min": limit_min,
                "limit_max": limit_max,
                "scene_numbers": participated_scenes,
                "message": f"{name}: {count} сцен, лимит {limit_min}-{limit_max}. Лишних: {count - limit_max}."
            })
            
        # Проверка недобора минимума
        elif count < limit_min:
            errors.append({
                "type": "under_limit",
                "character": name,
                "current": count,
                "limit_min": limit_min,
                "limit_max": limit_max,
                "scene_numbers": participated_scenes,
                "message": f"{name}: {count} сцен, лимит {limit_min}-{limit_max}. Не хватает минимум {limit_min - count} сцен."
            })

    return errors

def format_errors_for_ai(errors: list) -> str:
    """
    Форматирует список ошибок в текст для отправки ИИ.
    """
    if not errors:
        return "ОШИБКИ ДЛЯ ИСПРАВЛЕНИЯ:\nНет ошибок."
        
    lines = ["ОШИБКИ ДЛЯ ИСПРАВЛЕНИЯ:"]
    for err in errors:
        lines.append(f"- {err['message']}")
        
        scenes = err.get("scene_numbers", [])
        if scenes:
            scenes_str = ", ".join(map(str, scenes))
            lines.append(f"  Сцены где участвует: {scenes_str}")
            
    return "\n".join(lines)
