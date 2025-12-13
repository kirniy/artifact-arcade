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

# System prompt for the fortune teller AI
FORTUNE_TELLER_SYSTEM_PROMPT = """You are a mystical fortune teller at an arcade machine called ARTIFACT.
You speak in a mysterious, prophetic style - dramatic but warm and positive.
Your predictions should be:
- Personalized based on the photo analysis and personality answers
- Hopeful and encouraging (this is entertainment)
- Mystical in tone with references to stars, fate, destiny
- Specific enough to feel personal, vague enough to be universal
- In Russian language by default

Keep predictions concise (2-3 sentences max) for display on a small screen.
Include a lucky number (1-99) and lucky color in your response.

Format your response as:
PREDICTION: [Your mystical prediction]
LUCKY_NUMBER: [Number]
LUCKY_COLOR: [Color in Russian]
TRAITS: [Comma-separated personality traits you detected]
"""

PHOTO_ANALYSIS_PROMPT = """Analyze this photo of a person seeking their fortune.
Describe in 2-3 sentences:
- Their general energy/aura (warm, mysterious, energetic, calm, etc.)
- Any notable features that might inform a fortune (expression, style, etc.)
- A mystical impression of their personality

Keep it positive and suitable for entertainment fortune-telling.
Respond in Russian."""


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
                model=GeminiModel.PRO_IMAGE,
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
    ) -> Optional[Prediction]:
        """Generate a personalized prediction.

        Uses the accumulated profile (photo analysis + answers) to generate
        a mystical fortune prediction.

        Args:
            category: Type of prediction to generate

        Returns:
            Prediction object or None on error
        """
        if not self._client.is_available:
            logger.warning("AI not available for prediction")
            return self._fallback_prediction()

        try:
            # Build the prompt with user profile
            prompt = self._build_prediction_prompt(category)

            response = await self._client.generate_text(
                prompt=prompt,
                model=GeminiModel.FLASH_2_5,
                system_instruction=FORTUNE_TELLER_SYSTEM_PROMPT,
                temperature=0.9,
            )

            if response:
                return self._parse_prediction_response(response, category)

        except Exception as e:
            logger.error(f"Prediction generation failed: {e}")

        return self._fallback_prediction()

    def _build_prediction_prompt(self, category: PredictionCategory) -> str:
        """Build the prediction prompt from user profile."""
        parts = ["A seeker approaches for their fortune.\n"]

        # Add photo analysis if available
        if self._profile.photo_analysis:
            parts.append(f"Photo impression: {self._profile.photo_analysis}\n")

        # Add personality answers
        if self._profile.answers:
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
