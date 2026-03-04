from __future__ import annotations
import google.generativeai as genai

class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        genai.configure(api_key=api_key)
        self.model_name = model

    def generate(self, system_prompt: str, user_message: str, context: str = "") -> str:
        """
        Обычный запрос. Возвращает полный текст ответа.
        system_prompt + context объединяются в системный промпт.
        """
        full_system_prompt = f"{system_prompt}\n\n{context}".strip()
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=full_system_prompt
        )
        response = model.generate_content(user_message)
        return response.text

    def generate_stream(self, system_prompt: str, user_message: str, context: str = ""):
        """
        Генератор для стриминга. Yielдит чанки текста по мере получения.
        """
        full_system_prompt = f"{system_prompt}\n\n{context}".strip()
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=full_system_prompt
        )
        response = model.generate_content(user_message, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
