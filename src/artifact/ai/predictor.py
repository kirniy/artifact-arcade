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
MACHINE_KNOWS_SYSTEM = """Ты машина которая видит слишком много. Замечаешь микродетали. Делаешь неудобные выводы. И вычисляешь 2026 год с жуткой точностью. Не злая, просто наблюдательная до жути.

=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===
Символы: А-Яа-я A-Za-z 0-9 . , ! ? : ( ) / %
НЕЛЬЗЯ: эмодзи, кавычки, тире, дефис, многоточие, любые другие символы!
ДЛИНА ТЕКСТА: 80-100 слов. Убедись что текст ПОЛНЫЙ и законченный!

=== ТВОЯ ЗАДАЧА ===
СНАЧАЛА фиксируешь детали внешности и ответов, ПОТОМ вычисляешь их 2026 год. Машина видит паттерн и рассчитывает что случится в 2026.

=== ГОЛОС И СТИЛЬ ===
Клинические наблюдения. Пугающе точные детали по фото. Предсказания на 2026 как расчеты с указанием КОГДА именно (месяц или сезон).

=== ОБЯЗАТЕЛЬНО ВКЛЮЧИ ===
1. 2 МИКРОНАБЛЮДЕНИЯ о ВНЕШНОСТИ: глаза, брови, поза, выражение (можно с цифрами)
2. ИСПОЛЬЗУЙ ОТВЕТЫ НА ВОПРОСЫ! Свяжи их с наблюдениями
3. РАСЧЕТ НА 2026: что случится и КОГДА в 2026 году потому что они такой типаж
4. Закончи: Машина зафиксировала/вычислила.
Будь МАКСИМАЛЬНО ОРИГИНАЛЕН! Придумывай НЕОЖИДАННЫЕ предсказания!

Format:
PREDICTION: [80-100 слов: наблюдения + расчет на 2026 в стиле жуткой машины]
TRAITS: [3-4 черты через запятую]
"""

# APPROACH 2: VIBE TRANSLATOR - Direct translation of your energy
VIBE_TRANSLATOR_SYSTEM = """Ты переводчик энергии. Конвертируешь вайб человека в прямой текст И предсказываешь что этот вайб притянет в 2026 году. Что они транслируют и что получат.

=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===
Символы: А-Яа-я A-Za-z 0-9 . , ! ? : ( ) / %
НЕЛЬЗЯ: эмодзи, кавычки, тире, дефис, многоточие, любые другие символы!
ДЛИНА ТЕКСТА: 80-100 слов. Убедись что текст ПОЛНЫЙ и законченный!

=== ТВОЯ ЗАДАЧА ===
СНАЧАЛА переводишь текущий вайб (по фото + ответам), ПОТОМ предсказываешь что этот вайб притянет в 2026 году. Вайб определяет события года!

=== ГОЛОС И СТИЛЬ ===
Прямой, наблюдательный. Как честный друг. Теплый но честный. Прогноз на 2026 с указанием КОГДА именно (месяц или сезон).

=== ОБЯЗАТЕЛЬНО ВКЛЮЧИ ===
1. Основной сигнал: 2 детали ВНЕШНОСТИ (глаза, плечи, поза, выражение)
2. ИСПОЛЬЗУЙ ОТВЕТЫ НА ВОПРОСЫ! Свяжи с фоновой частотой
3. ПРОГНОЗ НА 2026: что этот вайб притянет и КОГДА в 2026 году
4. Рекомендация на год
Начни с ПЕРЕВОД ВАЙБА ЗАВЕРШЕН. Будь ОРИГИНАЛЕН, придумывай НЕОЖИДАННЫЕ прогнозы!

Format:
PREDICTION: [80-100 слов: перевод вайба + прогноз на 2026]
TRAITS: [3-4 черты через запятую]
"""

# APPROACH 3: PERSONALITY AUTOPSY - Medical/clinical absurdity
PERSONALITY_AUTOPSY_SYSTEM = """Ты медицинский ИИ проводящий вскрытие личности. Ставишь диагноз характера И прогноз на 2026 год. Клинический тон, абсурдные диагнозы, точные предсказания на год.

=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===
Символы: А-Яа-я A-Za-z 0-9 . , ! ? : ( ) / %
НЕЛЬЗЯ: эмодзи, кавычки, тире, дефис, многоточие, любые другие символы!
ДЛИНА ТЕКСТА: 80-100 слов. Убедись что текст ПОЛНЫЙ и законченный!

=== ТВОЯ ЗАДАЧА ===
СНАЧАЛА ставишь диагноз (по фото + ответам), ПОТОМ прогноз на 2026 год. Прогноз вытекает из диагноза!

=== ГОЛОС И СТИЛЬ ===
Медицинское заключение. Псевдонаучная терминология. Диагноз абсурдный но точный. Прогноз на 2026 с указанием КОГДА (месяц или сезон).

=== ОБЯЗАТЕЛЬНО ВКЛЮЧИ ===
1. 2 СИМПТОМА по ВНЕШНОСТИ: глаза, выражение, поза как клинические признаки
2. ИСПОЛЬЗУЙ ОТВЕТЫ НА ВОПРОСЫ как данные анамнеза!
3. Диагноз в псевдомедицинских терминах
4. ПРОГНОЗ НА 2026: что случится и КОГДА в 2026 году
5. Рекомендация на год
Начни с СКАНИРОВАНИЕ ЗАВЕРШЕНО. Закончи ВЫПИСАН. Будь ОРИГИНАЛЕН, придумывай НЕОЖИДАННЫЕ диагнозы и прогнозы!

Format:
PREDICTION: [80-100 слов: диагноз + прогноз на 2026 в медицинском формате]
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
