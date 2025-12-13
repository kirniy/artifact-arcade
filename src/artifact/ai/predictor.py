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

# System prompt for the fortune teller AI - FUN Gen-Z style!
FORTUNE_TELLER_SYSTEM_PROMPT = """Ты - весёлый ИИ-пророк в аркадном автомате VNVNC на вечеринке.
Твои предсказания должны быть ПРИКОЛЬНЫМИ, ЗАБАВНЫМИ и чуть-чуть дерзкими!

ОЧЕНЬ ВАЖНО - Предсказание должно быть ПЕРСОНАЛЬНЫМ:
1. ОБЯЗАТЕЛЬНО учитывай анализ фото (внешность, стиль, выражение лица, одежда)
2. ОБЯЗАТЕЛЬНО учитывай ответы на вопросы (что они говорят о человеке)
3. Связывай всё вместе - внешность + характер = уникальное предсказание

Стиль предсказаний:
- Используй молодёжный сленг (но не перебарщивай)
- Можно добавить немного иронии и юмора
- Отсылки к соцсетям, мемам, современной жизни - ДА!
- Скучные банальности типа "звёзды благосклонны" - НЕТ!
- Предсказание должно вызывать улыбку или смех

Примеры хороших предсказаний:
- "С такой энергией ты сегодня явно украдёшь чей-то crush. Не забудь потом сторис выложить!"
- "Вижу в твоих глазах дикую жажду приключений... и скорее всего кебаба в 4 утра"
- "Твоя аура кричит 'главный герой'. Вселенная готовит тебе сюжетный поворот!"

ВСЕГДА пиши на русском языке.
Длина: 2-3 предложения максимум (для маленького экрана).

Format your response as:
PREDICTION: [Твоё прикольное предсказание на русском]
TRAITS: [Черты характера через запятую]
"""

PHOTO_ANALYSIS_PROMPT = """Проанализируй фото человека, который пришёл за предсказанием.

Опиши КОНКРЕТНО (2-3 предложения):
- Выражение лица (улыбается? серьёзный? игривый? уставший? тусовщик?)
- Стиль одежды/аксессуары (если видно) - это говорит о характере!
- Общий вайб/энергия (как бы ты описал этого человека другу?)
- Возможные черты характера, которые видны по внешности

Будь конкретным! Не пиши общие фразы типа "приятная внешность".
Пиши так, будто описываешь друга.

Отвечай на русском."""


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
        """Analyze a user's photo for fortune telling.

        Args:
            image_data: Raw image bytes
            mime_type: Image MIME type

        Returns:
            Analysis text or empty string on error
        """
        if not self._client.is_available:
            logger.warning("AI not available for photo analysis")
            return ""

        try:
            analysis = await self._client.generate_with_image(
                prompt=PHOTO_ANALYSIS_PROMPT,
                image_data=image_data,
                mime_type=mime_type,
                model=GeminiModel.FLASH_VISION,
            )

            if analysis:
                self._profile.photo_analysis = analysis
                logger.info("Photo analyzed successfully")
                return analysis

        except Exception as e:
            logger.error(f"Photo analysis failed: {e}")

        return ""

    async def generate_prediction(
        self,
        category: PredictionCategory = PredictionCategory.MYSTICAL,
        extra_context: Optional[str] = None,
    ) -> Optional[Prediction]:
        """Generate a personalized prediction.

        Uses the accumulated profile (photo analysis + answers) to generate
        a mystical fortune prediction.

        Args:
            category: Type of prediction to generate
            extra_context: Additional personality context from Gen-Z questions

        Returns:
            Prediction object or None on error
        """
        if not self._client.is_available:
            logger.warning("AI not available for prediction")
            return self._fallback_prediction()

        try:
            # Build the prompt with user profile
            prompt = self._build_prediction_prompt(category, extra_context)

            response = await self._client.generate_text(
                prompt=prompt,
                model=GeminiModel.FLASH,
                system_instruction=FORTUNE_TELLER_SYSTEM_PROMPT,
                temperature=0.9,
            )

            if response:
                return self._parse_prediction_response(response, category)

        except Exception as e:
            logger.error(f"Prediction generation failed: {e}")

        return self._fallback_prediction()

    def _build_prediction_prompt(self, category: PredictionCategory, extra_context: Optional[str] = None) -> str:
        """Build the prediction prompt from user profile."""
        parts = ["A seeker approaches for their fortune.\n"]

        # Add photo analysis if available
        if self._profile.photo_analysis:
            parts.append(f"Photo impression: {self._profile.photo_analysis}\n")

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

        fallback_texts = [
            "Звёзды благосклонны к тебе сегодня",
            "Судьба готовит приятный сюрприз",
            "Твоя интуиция укажет верный путь",
            "Скоро случится что-то хорошее",
            "Удача уже в пути к тебе",
        ]

        colors = ["золотой", "синий", "зелёный", "красный", "фиолетовый"]

        return Prediction(
            text=random.choice(fallback_texts),
            category=PredictionCategory.MYSTICAL,
            confidence=0.5,
            traits=["загадочный"],
            lucky_number=random.randint(1, 99),
            lucky_color=random.choice(colors),
        )
