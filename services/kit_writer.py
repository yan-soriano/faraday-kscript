from __future__ import annotations

import os
import sqlite3
import uuid

class KitWriter:
    def __init__(self, kitsp_path: str):
        self.kitsp_path = kitsp_path
        self.backup_xml = None
        
    def _read_from_db(self) -> str:
        """Вспомогательный метод для чтения текущего XML из БД (нужен для backup-а)."""
        if not os.path.exists(self.kitsp_path):
            raise FileNotFoundError(f"Файл не найден: {self.kitsp_path}")
            
        try:
            conn = sqlite3.connect(self.kitsp_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT text FROM scenario LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                return row[0]
            return ""
        except sqlite3.OperationalError as e:
            raise RuntimeError(f"Файл заблокирован или недоступен: {e}")
        except Exception as e:
            raise RuntimeError(f"Ошибка при чтении из файла: {e}")

    def _write_to_db(self, xml_content: str) -> None:
        """Вспомогательный метод для записи XML в БД."""
        if not os.path.exists(self.kitsp_path):
            raise FileNotFoundError(f"Файл не найден: {self.kitsp_path}")
            
        try:
            conn = sqlite3.connect(self.kitsp_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("UPDATE scenario SET text = ? WHERE id = 1", (xml_content,))
            conn.commit()
            conn.close()
        except sqlite3.OperationalError as e:
            raise RuntimeError(f"Файл заблокирован или недоступен для записи: {e}")
        except Exception as e:
            raise RuntimeError(f"Ошибка при записи в файл проекта: {e}")

    def save_scene(self, raw_xml: str, target_uuid: str, new_scene_xml: str) -> str:
        """
        Заменяет XML одной сцены на новый, сохраняет backup и записывает в БД.
        Возвращает обновленный полный XML.
        """
        self.backup_xml = raw_xml
        
        start_tag = f'<scene_heading uuid="{target_uuid}">'
        start_idx = raw_xml.find(start_tag)
        
        if start_idx == -1:
            raise ValueError(f"Сцена с UUID {target_uuid} не найдена в XML.")
            
        # Ищем начало следующей сцены
        next_idx = raw_xml.find('<scene_heading', start_idx + len(start_tag))
        
        # Если это последняя сцена, ищем тег конца всего сценария
        if next_idx == -1:
            end_idx = raw_xml.rfind('</scenario>')
            if end_idx != -1:
                next_idx = end_idx
            else:
                next_idx = len(raw_xml)
                
        # Формируем новый XML сценария
        new_full_xml = raw_xml[:start_idx] + new_scene_xml.strip() + "\n" + raw_xml[next_idx:]
        
        # Обновляем БД
        self._write_to_db(new_full_xml)
        
        return new_full_xml

    def save_full_scenario(self, new_xml: str) -> None:
        """
        Полностью заменяет XML в таблице scenario.
        Используется, например, после поэпизодника или глобальных изменений.
        """
        current_xml = self._read_from_db()
        self.backup_xml = current_xml
        
        self._write_to_db(new_xml)

    def undo(self) -> bool:
        """
        Откатывает последнее изменение к сохраненному backup_xml.
        """
        if self.backup_xml is None:
            return False
            
        self._write_to_db(self.backup_xml)
        self.backup_xml = None
        return True

    def xml_to_kitsp_format(self, scene_text: str) -> str:
        """
        Конвертирует сгенерированный ИИ текст в XML формат Kit Scenarist.
        """
        lines = scene_text.split('\n')
        
        # Ищем первую и вторую непустые строки (по формату это Заголовок и Персонажи)
        non_empty_lines = [(i, l) for i, l in enumerate(lines) if l.strip()]
        if not non_empty_lines:
            return ""
            
        heading = non_empty_lines[0][1].strip()
        characters = ""
        start_idx = non_empty_lines[0][0] + 1
        
        if len(non_empty_lines) > 1:
            characters = non_empty_lines[1][1].strip()
            start_idx = non_empty_lines[1][0] + 1
            
        # Оставшийся текст
        remains = lines[start_idx:]
        
        new_uuid = f"{{{uuid.uuid4()}}}"
        
        xml_parts = []
        xml_parts.append(f'<scene_heading uuid="{new_uuid}">\n  <v><![CDATA[{heading}]]></v>\n</scene_heading>')
        
        if characters:
            xml_parts.append(f'<scene_characters>\n  <v><![CDATA[{characters}]]></v>\n</scene_characters>')
            
        current_block_type = None
        
        for line in remains:
            if not line.strip():
                current_block_type = None  # Сбрасываем тип блока на пустой строке
                continue
                
            orig_line = line
            l_str = line.strip()
            
            # Определяем наличие отступа
            is_indented = (len(orig_line) - len(orig_line.lstrip())) > 0
            
            # Проверяем на ВЕРХНИЙ РЕГИСТР (чтобы был текст из букв и всё капсом)
            is_upper = l_str.isupper() and any(c.isalpha() for c in l_str)
            
            # Если предыдущий блок был персонаж или ремарка - ожидаем ремарку или диалог
            if current_block_type in ['character', 'parenthetical']:
                if l_str.startswith('(') and l_str.endswith(')'):
                    xml_parts.append(f'<parenthetical>\n  <v><![CDATA[{l_str}]]></v>\n</parenthetical>')
                    current_block_type = 'parenthetical'
                else:
                    xml_parts.append(f'<dialog>\n  <v><![CDATA[{l_str}]]></v>\n</dialog>')
                    current_block_type = 'dialog'
                    
            elif is_indented:
                # В киноформате элементы с отступом это обычно блок Персонажа/Диалога/Ремарки
                if is_upper and not l_str.startswith('('):
                    xml_parts.append(f'<character>\n  <v><![CDATA[{l_str}]]></v>\n</character>')
                    current_block_type = 'character'
                elif l_str.startswith('(') and l_str.endswith(')'):
                    xml_parts.append(f'<parenthetical>\n  <v><![CDATA[{l_str}]]></v>\n</parenthetical>')
                    current_block_type = 'parenthetical'
                else:
                    xml_parts.append(f'<dialog>\n  <v><![CDATA[{l_str}]]></v>\n</dialog>')
                    current_block_type = 'dialog'
            else:
                # Если без отступа, но ИИ забыл его сделать (просто КАПС + короткая строка)
                if is_upper and not l_str.startswith('(') and len(l_str.split()) < 5:
                    xml_parts.append(f'<character>\n  <v><![CDATA[{l_str}]]></v>\n</character>')
                    current_block_type = 'character'
                else:
                    # По умолчанию без отступов работает блок "Действие" (Action)
                    xml_parts.append(f'<action>\n  <v><![CDATA[{l_str}]]></v>\n</action>')
                    current_block_type = 'action'
                    
        return "\n".join(xml_parts)
