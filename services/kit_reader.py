from __future__ import annotations

import os
import sqlite3
import xml.etree.ElementTree as ET

def _parse_scenes_from_xml(raw_xml: str) -> list:
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as e:
        raise ValueError(f"Ошибка парсинга XML: {e}")
        
    # Разделяем исходный XML на блоки сцен для сохранения точного 'full_xml'
    blocks = raw_xml.split('<scene_heading')
    
    scene_xmls = []
    for block in blocks[1:]:
        scene_xmls.append('<scene_heading' + block)
        
    scenes = []
    scene_idx = 0
    current_scene = None
    
    for child in root:
        if child.tag == 'scene_heading':
            # Если уже была сцена, сохраняем её
            if current_scene is not None:
                scenes.append(current_scene)
                
            uuid_val = child.attrib.get('uuid', '')
            v_tag = child.find('v')
            heading = v_tag.text.strip() if v_tag is not None and v_tag.text else ""
            
            # Извлекаем сырой XML этой сцены
            full_xml_str = scene_xmls[scene_idx] if scene_idx < len(scene_xmls) else ""
            scene_idx += 1
            
            full_xml_str = full_xml_str.strip()
            # Отрезаем закрывающий тег сценария, если он попал в блок последней сцены
            if full_xml_str.endswith('</scenario>'):
                full_xml_str = full_xml_str[:-len('</scenario>')].strip()
                
            current_scene = {
                "uuid": uuid_val,
                "index": len(scenes) + 1,
                "heading": heading,
                "participants": [],
                "action_text": None,
                "has_dialogue": False,
                "full_xml": full_xml_str
            }
        else:
            if current_scene is not None:
                if child.tag == 'scene_characters':
                    v_tag = child.find('v')
                    if v_tag is not None and v_tag.text:
                        chars = [c.strip().upper() for c in v_tag.text.split(',') if c.strip()]
                        for c in chars:
                            if c not in current_scene["participants"]:
                                current_scene["participants"].append(c)
                elif child.tag == 'action' and current_scene["action_text"] is None:
                    # Запоминаем только первый блок action
                    v_tag = child.find('v')
                    if v_tag is not None:
                        current_scene["action_text"] = (v_tag.text.strip() if v_tag.text else "")
                elif child.tag == 'dialog':
                    current_scene["has_dialogue"] = True

    # Сохраняем последнюю сцену
    if current_scene is not None:
        scenes.append(current_scene)
        
    return scenes


def load_project(kitsp_path: str) -> dict:
    if not os.path.exists(kitsp_path):
        raise FileNotFoundError(f"Файл проекта не найден: {kitsp_path}")
        
    try:
        conn = sqlite3.connect(kitsp_path)
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM scenario LIMIT 1")
        row = cursor.fetchone()
        conn.close()
    except sqlite3.DatabaseError as e:
        raise ValueError(f"Файл поврежден или не является базой SQLite (.kitsp): {e}")
    except Exception as e:
        raise ValueError(f"Ошибка при чтении файла проекта: {e}")
        
    if not row or not row[0]:
        raise ValueError("Таблица 'scenario' пуста или отсутствует колонка 'text'")
        
    raw_xml = row[0]
    scenes = _parse_scenes_from_xml(raw_xml)
    project_name = os.path.splitext(os.path.basename(kitsp_path))[0]
    
    return {
        "raw_xml": raw_xml,
        "scenes": scenes,
        "project_name": project_name
    }


def get_scene_by_uuid(raw_xml: str, uuid: str) -> dict | None:
    scenes = _parse_scenes_from_xml(raw_xml)
    for scene in scenes:
        if scene["uuid"] == uuid:
            return scene
    return None


def get_scenes_around(scenes: list, uuid: str, count: int = 1) -> dict:
    target_idx = -1
    for i, scene in enumerate(scenes):
        if scene["uuid"] == uuid:
            target_idx = i
            break
            
    if target_idx == -1:
        raise ValueError(f"Сцена с uuid {uuid} не найдена")
        
    start_idx = max(0, target_idx - count)
    end_idx = min(len(scenes), target_idx + count + 1)
    
    prev_scenes = scenes[start_idx:target_idx]
    next_scenes = scenes[target_idx + 1:end_idx]
    
    return {
        "prev": prev_scenes,
        "target": scenes[target_idx],
        "next": next_scenes
    }


def count_scenes_per_character(scenes: list) -> dict:
    counts = {}
    for scene in scenes:
        for participant in scene["participants"]:
            counts[participant] = counts.get(participant, 0) + 1
    return counts


def search_scenes_by_keywords(scenes: list, keywords: str) -> list:
    words = [w.lower() for w in keywords.split() if w.strip()]
    if not words:
        return []
        
    scored_scenes = []
    
    for scene in scenes:
        score = 0
        
        heading = (scene["heading"] or "").lower()
        for w in words:
            score += heading.count(w)
            
        for participant in scene["participants"]:
            p = participant.lower()
            for w in words:
                score += p.count(w)
                
        action = (scene["action_text"] or "").lower()
        for w in words:
            score += action.count(w)
            
        if score > 0:
            scored_scenes.append((score, scene))
            
    # Сортируем по количеству совпадений (по убыванию)
    scored_scenes.sort(key=lambda x: x[0], reverse=True)
    
    # Возвращаем максимум 3 сцены
    return [s[1] for s in scored_scenes[:3]]
