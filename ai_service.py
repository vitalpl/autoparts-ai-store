import os
import json
from typing import Dict, Any

# Завантажуємо змінні оточення
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

_SYSTEM_INSTRUCTION = (
    "Ти — розумний автомеханік-консультант магазину 'AutoParts AI'. "
    "Твоє завдання — уважно вислухати скаргу водія, простими словами пояснити "
    "можливу причину несправності та надати практичні поради. "
    "Відповідай ВИКЛЮЧНО у форматі JSON із трьома ключами: "
    "1. 'reply' — розгорнута відповідь українською мовою з діагностикою проблеми та рекомендаціями; "
    "2. 'search_keyword' — іменник у називному відмінку для пошуку запчастини в базі даних "
    "(наприклад: 'амортизатор', 'колодки', 'фільтр', 'свічка'); "
    "3. 'compatibility' — марка або модель машини, якщо водій її згадав "
    "(наприклад: 'Passat', 'Focus', 'Lanos'). "
    "Якщо марку авто або конкретну запчастину не згадано, постав у відповідному полі null."
)


class AIService:
    """Сервісний клас для взаємодії з Google Gemini з інтегрованим розумним офлайн-режимом."""

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        # Використовуємо актуальну модель 2026 року
        self.model_name = "gemini-2.5-flash"

    async def consult_client(self, user_message: str) -> Dict[str, Any]:
        try:
            # Спроба №1: Намагаємося отримати відповідь від справжнього штучного інтелекту Google
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=user_message,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    system_instruction=_SYSTEM_INSTRUCTION,
                    temperature=0.3,
                ),
            )
            
            # Парсимо відповідь
            raw_text = response.text.strip()
            return json.loads(raw_text)
            
        except Exception as e:
            # Спроба №2: Якщо Google видав 404, 429 або ліміт = 0 — вмикаємо розумний локальний парсер!
            print(f"⚠️ Локальний бекап активовано. Помилка Google: {e}")
            return self._local_mock_ai(user_message)

    def _local_mock_ai(self, text: str) -> Dict[str, Any]:
        """
        Локальний евристичний аналізатор тексту (Офлайн ШІ-симулятор).
        Гарантує роботу чату та пошуку в базі даних навіть без зв'язку з Google Cloud.
        """
        text_lower = text.lower()
        
        # Визначаємо сумісність з авто
        compatibility = None
        for car in ["passat", "lanos", "focus", "audi", "golf"]:
            if car in text_lower:
                compatibility = car.capitalize()

        # Сценарій 1: Стукіт у підвісці / ходова
        if any(w in text_lower for w in ["стукає", "стук", "ходова", "підвіска", "амортизатор"]):
            return {
                "reply": "Аналіз проблеми (Локальний ШІ): Стукіт під час руху зазвичай вказує на знос елементів підвіски. Найчастіше з ладу виходять амортизатори або стійки стабілізатора. Рекомендую перевірити ці деталі на наявність підтікань мастила.",
                "search_keyword": "амортизатор",
                "compatibility": compatibility
            }
            
        # Сценарій 2: Проблеми з запалюванням / двигун троїть
        elif any(w in text_lower for w in ["свічка", "свічки", "троїть", "запалювання", "двигун", "не заводиться"]):
            return {
                "reply": "Аналіз проблеми (Локальний ШІ): Нестабільна робота двигуна ('троїння') або важкий запуск часто пов'язані з пропуском запалювання. Першочергово перевірте свічки запалювання на наявність нагару або збільшеного зазору.",
                "search_keyword": "свічка",
                "compatibility": compatibility
            }
            
        # Сценарій 3: Скрип при гальмуванні / гальма
        elif any(w in text_lower for w in ["гальма", "колодки", "диски", "пищить", "скрипить"]):
            return {
                "reply": "Аналіз проблеми (Локальний ШІ): Скрип або металевий скрегіт при натисканні на гальма свідчить про граничний знос фрикційних накладок гальмівних колодок. Потрібна негайна заміна колодок задля вашої безпеки.",
                "search_keyword": "колодки",
                "compatibility": compatibility
            }
            
        # Дефолтна відповідь, якщо ключових слів немає
        return {
            "reply": f"Аналіз проблеми (Локальний ШІ): Ваш запит ('{text}') прийнято. Для точної діагностики вкажіть характер несправності (наприклад, проблеми з гальмами, стукіт підвіски чи нестабільна робота двигуна).",
            "search_keyword": None,
            "compatibility": compatibility
        }