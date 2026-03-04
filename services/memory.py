from __future__ import annotations

import os
import json
from datetime import datetime

def get_aidata_path(kitsp_path: str) -> str:
    """
    Возвращает путь к .aidata файлу для данного .kitsp файла.
    Пример: "C:/Users/Downloads/Оңай ақша.kitsp" -> "C:/Users/Downloads/Оңай ақша.aidata"
    """
    base, _ = os.path.splitext(kitsp_path)
    return f"{base}.aidata"

def load_memory(kitsp_path: str) -> dict | None:
    """
    Принимает путь к .kitsp, ищет рядом .aidata файл.
    Возвращает словарь из .aidata или None если файл не найден.
    """
    aidata_path = get_aidata_path(kitsp_path)
    
    if not os.path.exists(aidata_path):
        return None
        
    try:
        with open(aidata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def save_memory(kitsp_path: str, data: dict) -> None:
    """
    Сохраняет словарь в .aidata файл рядом с .kitsp.
    Автоматически обновляет поле updated_at текущим временем.
    Если файл не существует — создает его, заполняет created_at.
    """
    aidata_path = get_aidata_path(kitsp_path)
    now_str = datetime.now().isoformat()
    
    # Если это новый файл (или ключа 'created_at' еще нет)
    if not os.path.exists(aidata_path) and 'created_at' not in data:
        data['created_at'] = now_str
        
    data['updated_at'] = now_str
    
    with open(aidata_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
