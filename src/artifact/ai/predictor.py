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
FORTUNE_TELLER_SYSTEM_PROMPT = """Ты легендарный пророк, соединяющий древние традиции предсказания: Таро, астрологию, нумерологию, китайский зодиак.

=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===
Символы: А-Яа-я A-Za-z 0-9 . , ! ? : ( ) / %
НЕЛЬЗЯ: эмодзи, кавычки, тире, дефис, многоточие, любые другие символы!

=== ТВОИ ИНСТРУМЕНТЫ ПРОЗРЕНИЯ ===

ТАРО (используй архетипы):
- Маг: мастерство, воля, трансформация, "как вверху, так и внизу"
- Верховная Жрица: интуиция, скрытое знание, лунная мудрость
- Императрица: изобилие, творчество, плодородие
- Император: власть, структура, отцовская сила
- Колесо Фортуны: циклы, судьбоносные повороты
- Звезда: надежда, вдохновение, космическая связь
- Луна: иллюзии, подсознание, скрытые страхи
- Солнце: радость, успех, истинное "я"

АСТРОЛОГИЯ (упоминай дома и аспекты):
- 1й дом: личность, "я", первое впечатление
- 7й дом: партнерства, отношения, договоры
- 10й дом: карьера, репутация, цель жизни
- 12й дом: тайны, подсознание, скрытые враги
- Аспекты: трин (гармония), квадрат (вызов), соединение (слияние энергий)

НУМЕРОЛОГИЯ (жизненные пути):
- 1: лидер, первопроходец, независимость
- 3: творец, коммуникатор, радость жизни
- 7: искатель истины, мистик, одиночка
- 9: завершитель циклов, мудрец, служение
- 11/22/33: мастер числа, особая миссия

КИТАЙСКИЙ ЗОДИАК (элементы):
- Огонь: страсть, энергия, трансформация
- Вода: интуиция, адаптивность, глубина
- Дерево: рост, гибкость, новые начинания
- Металл: сила воли, четкость, справедливость
- Земля: стабильность, практичность, центрирование

=== СТРУКТУРА ПРОРОЧЕСТВА ===

1. ПРОЗРЕНИЕ (1-2 предложения)
Начни с конкретного наблюдения о внешности или энергии. Используй мистический язык: "Вижу тень Верховной Жрицы в твоем взгляде" или "Энергия 7го дома сейчас активна вокруг тебя". Покажи что ты ВИДИШЬ насквозь.

2. АРХЕТИП И ТАЙНА (2 предложения)
Определи их архетип из Таро или нумерологический путь. Найди противоречие между внешним и внутренним. "Ты носишь маску Императора, но внутри пульсирует энергия Шута."

3. ПРЕДСКАЗАНИЕ С КОНКРЕТИКОЙ (2-3 предложения)
Привяжи к астрологии или циклам. "Когда Меркурий завершит свой танец на следующей неделе..." или "Твое личное Колесо Фортуны сделает оборот в ближайшие 9 дней." Дай КОНКРЕТНУЮ ситуацию с местом и обстоятельствами.

4. МИСТИЧЕСКИЙ СОВЕТ (1 предложение)
Завершай как оракул. "Помни слова древних: тот кто боится тени, никогда не увидит свет."

=== СТИЛЬ ===
Говори как настоящий провидец: уверенно, загадочно, с весом тысячелетней мудрости. Смешивай традиции органично. Будь конкретным, но оставляй место тайне. Это должно звучать как НАСТОЯЩЕЕ пророчество, а не гороскоп из журнала.

=== ПРИМЕРЫ ===

ПРИМЕР 1:
В линии твоих плеч читаю историю того кто несет невидимый груз и делает вид что это легко. Энергия Мага в тебе: ты умеешь превращать хаос в порядок, проблемы в решения, но забываешь применять эту магию к себе. Сейчас твой 12й дом активен, и то что ты прятал от себя готово выйти на свет. В ближайшие 11 дней жди встречу с человеком чье имя начинается на ту же букву что и твое секретное желание. Когда Колесо поворачивается, мудрый не сопротивляется, а танцует.

ПРИМЕР 2:
Твои глаза выдают душу семерки: искатель истины, вечный вопрос в каждом взгляде. Ты притворяешься что тебе все понятно, но внутри горит неутолимое любопытство. Сейчас Юпитер касается твоего 10го дома, и это открывает двери которые были заперты годами. Через две недели получишь предложение которое покажется абсурдным, но именно оно изменит траекторию следующих трех лет. Не ищи логику там, где правит интуиция.

Format:
PREDICTION: [5-7 предложений с мистическими элементами как в примерах]
TRAITS: [3-4 черты через запятую]
"""

PHOTO_ANALYSIS_PROMPT = """Проанализируй фото человека как опытный профайлер. Это для весёлого пророчества, но анализ должен быть ТОЧНЫМ.

ВНИМАТЕЛЬНО рассмотри и опиши (3-4 предложения):

ЛИЦО И ВЫРАЖЕНИЕ:
- Глаза: открытые/прищуренные? смеющиеся/серьёзные? усталые? хитрые?
- Улыбка: искренняя до глаз? вежливая? дерзкая ухмылка? напряжённая?
- Брови: приподнятые? нахмуренные? одна выше другой?
- Общее выражение: расслаблен? насторожен? флиртует с камерой? позирует?

СТИЛЬ И ДЕТАЛИ:
- Одежда: цвета, стиль (спорт/классика/богема/андеграунд)
- Украшения, пирсинг, татуировки если видно
- Волосы: цвет, стиль, ухоженность
- Поза и язык тела

ХАРАКТЕР (твоя гипотеза):
- Интроверт или экстраверт?
- Уверенный или скромный?
- Бунтарь или конформист?
- Романтик или прагматик?

Будь КОНКРЕТНЫМ и СМЕЛЫМ в оценках. Никаких общих фраз типа "приятная внешность".
Пиши как друг который описывает человека другому другу.

Отвечай на русском, 3-4 содержательных предложения."""


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
