from __future__ import annotations

LIMITS = {
    "main":      {"min": 15, "max": 20},
    "secondary": {"min": 0,  "max": 7},
    "adult":     {"min": 0,  "max": 10},
}
MAX_ADULTS = 4
SCENE_COUNT_MIN = 40
SCENE_COUNT_MAX = 45
MAX_DIFF_BETWEEN_MAIN = 3

def validate_structure(scenes: list, characters: list) -> list:
    """
    Проверяет лимиты участия персонажей в сценах, общего количества сцен и взрослых.
    Возвращает список словарей с ошибками. Если ошибок нет — пустой список.
    """
    errors = []
    
    total_scenes = len(scenes)
    # Проверка общего количества сцен (от 40 до 45)
    if total_scenes < SCENE_COUNT_MIN or total_scenes > SCENE_COUNT_MAX:
        errors.append({
            "type": "wrong_scene_count",
            "character": None,
            "current": total_scenes,
            "limit_min": SCENE_COUNT_MIN,
            "limit_max": SCENE_COUNT_MAX,
            "scene_numbers": [],
            "message": f"Общее количество сцен: {total_scenes}, требуется {SCENE_COUNT_MIN}-{SCENE_COUNT_MAX}."
        })
        
    # Проверка на общее количество взрослых персонажей
    adult_count = sum(1 for c in characters if c.get("role_type") == "adult")
    if adult_count > MAX_ADULTS:
        errors.append({
            "type": "too_many_adults",
            "character": None,
            "current": adult_count,
            "limit_min": 0,
            "limit_max": MAX_ADULTS,
            "scene_numbers": [],
            "message": f"Взрослых персонажей: {adult_count}, максимум {MAX_ADULTS}."
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
                
    main_counts = {}

    # Проверяем лимиты по каждому персонажу
    for char_info in characters:
        name = char_info.get("name", "").upper()
        role = char_info.get("role_type")
        
        participated_scenes = char_scenes.get(name, [])
        count = len(participated_scenes)
        
        limit_min = 0
        limit_max = 9999
        
        if role == "main":
            limit_min = LIMITS["main"]["min"]
            limit_max = LIMITS["main"]["max"]
            main_counts[name] = count
        elif role == "secondary":
            limit_min = LIMITS["secondary"]["min"]
            limit_max = LIMITS["secondary"]["max"]
        elif role == "adult":
            limit_min = LIMITS["adult"]["min"]
            limit_max = LIMITS["adult"]["max"]
            
        # Проверка "ни в одной сцене"
        if count == 0 and limit_min > 0:
            errors.append({
                "type": "missing_character",
                "character": name,
                "current": 0,
                "limit_min": limit_min,
                "limit_max": limit_max,
                "scene_numbers": [],
                "message": f"{name} не участвует ни в одной сцене, а требуется минимум {limit_min}."
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

    # Проверка разницы между главными персонажами
    if main_counts:
        max_name = max(main_counts, key=main_counts.get)
        min_name = min(main_counts, key=main_counts.get)
        max_count = main_counts[max_name]
        min_count = main_counts[min_name]
        
        if max_count - min_count > MAX_DIFF_BETWEEN_MAIN:
            errors.append({
                "type": "uneven_distribution",
                "character": None,
                "current": max_count - min_count,
                "limit_min": 0,
                "limit_max": MAX_DIFF_BETWEEN_MAIN,
                "scene_numbers": [],
                "message": f"Негізгі кейіпкерлер арасындағы айырмашылық тым үлкен: \n{max_name}: {max_count} сцен, {min_name}: {min_count} сцен (айырмашылық: {max_count - min_count}, максимум: {MAX_DIFF_BETWEEN_MAIN})"
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
