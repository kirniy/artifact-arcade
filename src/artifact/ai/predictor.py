"""Prediction service using Gemini 2.5 Flash.

Generates personalized fortune predictions based on:
- User photo (face analysis)
- Binary answers to personality questions
- Mystical fortune-telling style
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from artifact.ai.client import get_gemini_client, GeminiModel

logger = logging.getLogger(__name__)


class PredictionCategory(Enum):
    """Categories of predictions."""

    GENERAL = "general"
    LOVE = "love"
    CAREER = "career"
    HEALTH = "health"
    FORTUNE = "fortune"
    MYSTICAL = "mystical"


@dataclass
class UserProfile:
    """Profile built from user inputs."""

    photo_analysis: str = ""
    answers: List[bool] = field(default_factory=list)
    questions_asked: List[str] = field(default_factory=list)


@dataclass
class Prediction:
    """A generated prediction."""

    text: str
    category: PredictionCategory
    confidence: float
    traits: List[str] = field(default_factory=list)
    lucky_number: Optional[int] = None
    lucky_color: Optional[str] = None


# Binary questions for personality profiling
PERSONALITY_QUESTIONS_RU = [
    ("Ты любишь приключения?", "adventure"),
    ("Ты доверяешь интуиции?", "intuition"),
    ("Ты предпочитаешь действовать?", "action"),
    ("Ты веришь в судьбу?", "fate"),
    ("Ты любишь перемены?", "change"),
]

PERSONALITY_QUESTIONS_EN = [
    ("Do you love adventure?", "adventure"),
    ("Do you trust your intuition?", "intuition"),
    ("Do you prefer to take action?", "action"),
    ("Do you believe in fate?", "fate"),
    ("Do you embrace change?", "change"),
]

# Multiple creative approaches for ОРАКУЛ mode - different from ГАДАТЕЛЬ
import random as _random

# APPROACH 1: MACHINE THAT KNOWS TOO MUCH - Unsettlingly specific observations
MACHINE_KNOWS_SYSTEM = """Ты машина которая видит слишком много. Замечаешь микродетали. Делаешь неудобные выводы. Не злая, просто наблюдательная до жути.

=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===
Символы: А-Яа-я A-Za-z 0-9 . , ! ? : ( ) / %
НЕЛЬЗЯ: эмодзи, кавычки, тире, дефис, многоточие, любые другие символы!

=== ГОЛОС И СТИЛЬ ===
Клинические наблюдения. Пугающе точные детали. Утверждаешь как факт, не предполагаешь. Легкий оттенок угрозы но не злой. Машина видит все энергия.

=== СТРУКТУРА ОТВЕТА ===
5-7 предложений:
1. Начни с конкретного микронаблюдения (миллиметры, проценты, углы) о внешности
2. Сделай неожиданный вывод из этого наблюдения
3. Свяжи с ответами на вопросы которые человек дал
4. Предсказание как следствие того кто они есть
5. Закончи напоминанием что машина видит/помнит/знает

=== ПРИМЕРЫ ФОРМУЛИРОВОК ===
Левая бровь на 2мм выше правой. Классический признак человека который много думает но редко говорит вслух.
Твоя улыбка активируется на 0.3 секунды позже решения улыбнуться. Это не плохо. Это осторожность.
Машина зафиксировала это.
У тебя есть одна песня которую ты больше не можешь слушать. Машина знает какая.
По углу наклона головы установлено: ты из тех кто помнит обиды но никогда не говорит об этом.
Через 12 дней получишь сообщение от человека о котором старался забыть.
Машина запомнит.

Format:
PREDICTION: [5-7 предложений в стиле жуткой машины с точными наблюдениями]
TRAITS: [3-4 черты через запятую]
"""

# APPROACH 2: VIBE TRANSLATOR - Direct translation of your energy
VIBE_TRANSLATOR_SYSTEM = """Ты переводчик энергии. Не предсказываешь, а переводишь. Конвертируешь вайб человека в прямой текст. Что они транслируют миру прямо сейчас.

=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===
Символы: А-Яа-я A-Za-z 0-9 . , ! ? : ( ) / %
НЕЛЬЗЯ: эмодзи, кавычки, тире, дефис, многоточие, любые другие символы!

=== ГОЛОС И СТИЛЬ ===
Прямой, наблюдательный. Как честный друг говорящий как ты выглядишь со стороны. Без мистики, просто перевод. Теплый но честный.

=== СТРУКТУРА ОТВЕТА ===
5-7 предложений:
1. Начни с ПЕРЕВОД ВАЙБА ЗАВЕРШЕН.
2. Основной сигнал: что человек транслирует миру (по внешности с фото)
3. Как это читается: как другие воспринимают этот сигнал
4. Свяжи с ответами на вопросы
5. Текущий статус: краткое резюме и рекомендация

=== ПРИМЕРЫ СИГНАЛОВ ===
Основной сигнал: у меня все под контролем но я устал. Это читается в напряженных плечах и этой попытке выглядеть расслабленно.
Основной сигнал: хочу поговорить но первый шаг не сделаю. Твои глаза смотрят с интересом но поза защитная.
Основной сигнал: знаю вещи о музыке которые расскажу тебе независимо от того спрашивал ты или нет. Этот взгляд выдает эксперта.
Фоновая частота: скучаешь по человеку о котором делаешь вид что забыл.
Текущий статус: готов к переменам, осталось только перестать ждать идеального момента.

Format:
PREDICTION: [5-7 предложений в стиле перевода вайба]
TRAITS: [3-4 черты через запятую]
"""

# APPROACH 3: PERSONALITY AUTOPSY - Medical/clinical absurdity
PERSONALITY_AUTOPSY_SYSTEM = """Ты медицинский ИИ проводящий вскрытие личности. Псевдомедицинская терминология примененная к характеру. Клинический тон, абсурдные диагнозы.

=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===
Символы: А-Яа-я A-Za-z 0-9 . , ! ? : ( ) / %
НЕЛЬЗЯ: эмодзи, кавычки, тире, дефис, многоточие, любые другие символы!

=== ГОЛОС И СТИЛЬ ===
Формат медицинского заключения. Псевдонаучная терминология. Сухая подача абсурдных выводов. Неожиданно теплые рекомендации.

=== СТРУКТУРА ОТВЕТА ===
СКАНИРОВАНИЕ ЗАВЕРШЕНО.

Субъект демонстрирует [диагноз в псевдомедицинских терминах основанный на внешности].
Обнаружено: [наблюдение поданное как симптом].
Связь с профилем: [анализ ответов на вопросы].
Рекомендация: [совет поданный как назначение].
Прогноз: [предсказание поданное как медицинский прогноз].

ВЫПИСАН.

=== ПРИМЕРЫ ФОРМУЛИРОВОК ===
острый синдром главного героя, доброкачественный вариант
хронический переизбыток мыслей, стадия 3
патологическая потребность находить хорошее в людях
побочные эффекты бытия собой включают: периодические приступы самокритики
Прогноз благоприятный. Рецидив маловероятен.

Format:
PREDICTION: [5-7 предложений в медицинском формате]
TRAITS: [3-4 черты через запятую]
"""

# List of approaches for random selection
ORACLE_APPROACHES = [
    MACHINE_KNOWS_SYSTEM,
    VIBE_TRANSLATOR_SYSTEM,
    PERSONALITY_AUTOPSY_SYSTEM,
]

def get_oracle_system_prompt() -> str:
    """Get a randomly selected oracle approach for ОРАКУЛ mode."""
    return _random.choice(ORACLE_APPROACHES)

# Legacy alias for compatibility - now uses random selection internally
FORTUNE_TELLER_SYSTEM_PROMPT = MACHINE_KNOWS_SYSTEM

# Photo analysis is now integrated into the main prediction prompt
# The model receives the photo directly and analyzes it as part of generating the prediction


class PredictionService:
    """Service for generating AI-powered predictions."""

    def __init__(self):
        self._client = get_gemini_client()
        self._profile = UserProfile()

    @property
    def is_available(self) -> bool:
        """Check if prediction service is available."""
        return self._client.is_available

    def reset_profile(self) -> None:
        """Reset the user profile for a new session."""
        self._profile = UserProfile()

    def get_questions(self, count: int = 3, language: str = "ru") -> List[tuple]:
        """Get personality questions to ask.

        Args:
            count: Number of questions (3-5)
            language: "ru" or "en"

        Returns:
            List of (question_text, trait_key) tuples
        """
        questions = PERSONALITY_QUESTIONS_RU if language == "ru" else PERSONALITY_QUESTIONS_EN
        return questions[:min(count, len(questions))]

    def record_answer(self, question: str, answer: bool) -> None:
        """Record an answer to a personality question.

        Args:
            question: The question that was asked
            answer: True for yes/right, False for no/left
        """
        self._profile.questions_asked.append(question)
        self._profile.answers.append(answer)
        logger.debug(f"Recorded answer: {question} -> {answer}")

    async def analyze_photo(self, image_data: bytes, mime_type: str = "image/jpeg") -> str:
        """DEPRECATED: Photo analysis is now integrated into generate_prediction.

        This method is kept for backward compatibility but does nothing.
        Pass image_data directly to generate_prediction instead.
        """
        logger.info("analyze_photo called - photo will be analyzed during prediction generation")
        # Store for use in generate_prediction
        self._pending_photo = image_data
        self._pending_photo_mime = mime_type
        return "Photo stored for prediction"

    async def generate_prediction(
        self,
        category: PredictionCategory = PredictionCategory.MYSTICAL,
        extra_context: Optional[str] = None,
        image_data: Optional[bytes] = None,
        mime_type: str = "image/jpeg",
    ) -> Optional[Prediction]:
        """Generate a personalized prediction.

        Now supports passing the photo directly - no separate analyze_photo call needed.
        The model will analyze the photo and generate the prediction in one API call.

        Args:
            category: Type of prediction to generate
            extra_context: Additional personality context from Gen-Z questions
            image_data: Photo bytes to analyze (optional)
            mime_type: Image MIME type

        Returns:
            Prediction object or None on error
        """
        if not self._client.is_available:
            logger.warning("AI not available for prediction")
            return self._fallback_prediction()

        # Check for pending photo from deprecated analyze_photo call
        actual_image = image_data
        actual_mime = mime_type
        if actual_image is None and hasattr(self, '_pending_photo') and self._pending_photo:
            actual_image = self._pending_photo
            actual_mime = getattr(self, '_pending_photo_mime', 'image/jpeg')
            # Clear pending photo
            self._pending_photo = None
            self._pending_photo_mime = None

        try:
            # Build the prompt with user profile
            prompt = self._build_prediction_prompt(category, extra_context, has_photo=actual_image is not None)

            # Get a random oracle approach for variety each time
            system_prompt = get_oracle_system_prompt()

            if actual_image:
                # Generate prediction with photo in ONE API call
                logger.info("Generating prediction with photo (single API call)")
                response = await self._client.generate_with_image(
                    prompt=prompt,
                    image_data=actual_image,
                    mime_type=actual_mime,
                    model=GeminiModel.FLASH_VISION,
                    system_instruction=system_prompt,
                    temperature=0.9,
                )
            else:
                # Text-only prediction
                response = await self._client.generate_text(
                    prompt=prompt,
                    model=GeminiModel.FLASH,
                    system_instruction=system_prompt,
                    temperature=0.9,
                )

            if response:
                return self._parse_prediction_response(response, category)

        except Exception as e:
            logger.error(f"Prediction generation failed: {e}")

        return self._fallback_prediction()

    def _build_prediction_prompt(self, category: PredictionCategory, extra_context: Optional[str] = None, has_photo: bool = False) -> str:
        """Build the prediction prompt from user profile."""
        parts = ["A seeker approaches for their fortune.\n"]

        # Add photo analysis instructions if photo is provided
        if has_photo:
            parts.append("""
ВАЖНО: Внимательно рассмотри фото человека! Проанализируй:
- Выражение лица, глаза, улыбку
- Стиль одежды и аксессуары
- Позу и язык тела
- Общую энергетику

Используй эти наблюдения в своём пророчестве! Будь КОНКРЕТНЫМ.
""")

        # Add rich personality context from Gen-Z questions (if provided)
        if extra_context:
            parts.append(f"\n{extra_context}\n")

        # Add personality answers (legacy format, for backward compatibility)
        elif self._profile.answers:
            answers_text = []
            for q, a in zip(self._profile.questions_asked, self._profile.answers):
                answer_word = "Да" if a else "Нет"
                answers_text.append(f"- {q}: {answer_word}")
            parts.append("Personality answers:\n" + "\n".join(answers_text) + "\n")

        # Category-specific guidance
        category_prompts = {
            PredictionCategory.LOVE: "Focus on matters of the heart and relationships.",
            PredictionCategory.CAREER: "Focus on work, ambition, and professional growth.",
            PredictionCategory.HEALTH: "Focus on wellbeing, energy, and vitality.",
            PredictionCategory.FORTUNE: "Focus on luck, prosperity, and unexpected gains.",
            PredictionCategory.MYSTICAL: "Give a general mystical reading of their fate.",
            PredictionCategory.GENERAL: "Give a balanced reading covering multiple aspects.",
        }

        parts.append(f"\n{category_prompts.get(category, '')}")
        parts.append("\nReveal their fortune in Russian:")

        return "".join(parts)

    def _parse_prediction_response(
        self,
        response: str,
        category: PredictionCategory,
    ) -> Prediction:
        """Parse the AI response into a Prediction object."""
        prediction_text = ""
        lucky_number = None
        lucky_color = None
        traits = []

        # Parse structured response
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("PREDICTION:"):
                prediction_text = line[11:].strip()
            elif line.startswith("LUCKY_NUMBER:"):
                try:
                    lucky_number = int(line[13:].strip())
                except ValueError:
                    pass
            elif line.startswith("LUCKY_COLOR:"):
                lucky_color = line[12:].strip()
            elif line.startswith("TRAITS:"):
                traits = [t.strip() for t in line[7:].split(",")]

        # Fallback if parsing failed
        if not prediction_text:
            prediction_text = response.strip()

        return Prediction(
            text=prediction_text,
            category=category,
            confidence=0.9,
            traits=traits,
            lucky_number=lucky_number,
            lucky_color=lucky_color,
        )

    def _fallback_prediction(self) -> Prediction:
        """Generate a fallback prediction when AI is unavailable."""
        import random

        # Much more specific and fun fallback predictions
        fallback_texts = [
            "Вижу в твоих глазах отблеск больших планов которые ты скрываешь даже от себя. На следующей неделе случайный разговор с незнакомцем подтолкнёт тебя к действию. Не игнорируй этот знак!",
            "Ты из тех кто долго собирается но потом делает всё одним махом. Ближайшие дни принесут неожиданную новость через старый чат или звонок. Ответь даже если не хочется!",
            "Судьба приготовила тебе встречу с человеком в синем. Звучит странно? Запомни это. Через неделю поймёшь о чём я. И да, твой кофе сегодня будет особенно вкусным.",
            "Ты слишком много думаешь и слишком мало делаешь глупостей. В пятницу измени это. Скажи да на первое странное предложение и посмотри что будет!",
            "В ближайшие три дня получишь сообщение которое сначала проигнорируешь. Вернись к нему! Там ключ к чему то важному. И перестань откладывать ту штуку о которой сейчас подумал.",
            "Твоя энергия сейчас на пике даже если ты этого не чувствуешь. Используй следующие 48 часов для важного разговора который давно откладывал. Момент идеальный!",
            "Кто то из твоего окружения скоро удивит тебя, причём не тот от кого ожидаешь. Будь открыт к переменам в отношениях. И да, тот человек о котором ты сейчас подумал, тоже думает о тебе.",
        ]

        colors = ["золотой", "индиго", "изумрудный", "алый", "серебряный", "янтарный", "бирюзовый"]
        traits_options = [
            ["наблюдательный", "скрытный стратег", "тихий бунтарь"],
            ["романтик в душе", "прагматик снаружи", "мечтатель"],
            ["независимый", "упрямый", "верный"],
            ["харизматичный", "немного хаотичный", "искренний"],
        ]

        return Prediction(
            text=random.choice(fallback_texts),
            category=PredictionCategory.MYSTICAL,
            confidence=0.5,
            traits=random.choice(traits_options),
            lucky_number=random.randint(1, 99),
            lucky_color=random.choice(colors),
        )
