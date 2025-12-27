"""Word bank for RapTrack mode.

Fun, Gen-Z, Russian rapper-inspired words and phrases.
Playing on stereotypes, memes, and rapper culture.
"""

import random
from typing import List, Dict, Optional
from dataclasses import dataclass
import json
from pathlib import Path

# =============================================================================
# WORD CATEGORIES - Russian Rap / Gen-Z / Club Culture
# =============================================================================

WORDS: Dict[str, List[str]] = {
    # Rapper names and references (для вирусности)
    "рэперы": [
        "Oxxxymiron", "Скриптонит", "Моргенштерн", "Pharaoh",
        "Хаски", "Face", "Баста", "Элджей", "Kizaru", "Платина",
        "Big Baby Tape", "Lil Krystalll", "Mayot", "Feduk",
        "Слава КПСС", "Гнойный", "ATL", "Томас Мраз",
    ],

    # Бренды и флекс
    "флекс": [
        "Gucci", "Balenciaga", "Off-White", "Supreme", "Versace",
        "G-Wagon", "Porsche", "Rolex", "Cartier", "Louis",
        "iced out", "drip", "стиль", "лук", "шмот",
        "брилики", "цепь", "перстень", "тачка", "бентли",
    ],

    # Сленг и мемы Gen-Z
    "сленг": [
        "вайб", "краш", "флекс", "хайп", "панч",
        "рофл", "кринж", "чилл", "движ", "изи",
        "трэп", "буст", "скам", "фит", "бэнгер",
        "слэп", "респект", "хейтер", "фанат", "ор",
    ],

    # Клуб и ночь
    "клуб": [
        "шот", "VIP", "танцпол", "бар", "диджей",
        "стробоскоп", "неон", "дым", "сабвуфер", "бит",
        "секьюрити", "фейсконтроль", "бутылка", "столик", "после трёх",
        "до утра", "такси домой", "номерок", "гардероб", "тусовка",
    ],

    # Эмоции и состояния
    "эмоции": [
        "дерзкий", "грустный", "влюблённый", "злой", "на вайбе",
        "усталый", "в потоке", "одинокий", "на движе", "королём",
        "в депрессии", "счастливый", "пьяный", "трезвый", "в угаре",
        "тревожный", "спокойный", "бешеный", "ленивый", "голодный",
    ],

    # Действия (глаголы)
    "действия": [
        "флексить", "читать", "качать", "двигать", "жечь",
        "качаю", "ловлю", "кидаю", "врываюсь", "исчезаю",
        "улетаю", "падаю", "прыгаю", "бегу", "молчу",
        "кричу", "шепчу", "танцую", "плачу", "смеюсь",
    ],

    # Места (Питер и не только)
    "места": [
        "Питер", "Москва", "блок", "район", "подъезд",
        "крыша", "двор", "улица", "мост", "набережная",
        "метро", "маршрутка", "остановка", "парковка", "заправка",
        "макдак", "шаверма", "магаз", "аптека", "круглосуточный",
    ],

    # Абсурд и рандом (для смеха)
    "абсурд": [
        "шаурма", "кот", "бабушка", "сосед", "почтальон",
        "пельмени", "борщ", "дача", "гараж", "батя",
        "маршрутка", "пятёрочка", "доширак", "кипяток", "чайник",
        "тапки", "халат", "сигарета", "зажигалка", "жвачка",
    ],

    # Мета/мемы про рэп
    "мета": [
        "бит от Канье", "продакшн", "лейбл", "контракт", "релиз",
        "фристайл", "баттл", "дисс", "фит с", "куплет",
        "припев", "ad-lib", "автотюн", "flow", "барс",
        "рифма", "стаф", "хук", "аутро", "интро",
    ],
}

# =============================================================================
# JOKER RULES - Special modifiers for lyrics generation
# =============================================================================

JOKER_RULES: List[str] = [
    "Строка ТОЛЬКО перечисление",
    "Вставь ЭЙ после строки",
    "Припев из 4 слов макс",
    "Одна строка шепотом",
    "Упомяни погоду",
    "Последняя строка вопрос",
    "Добавь БАМ ПАУ УУ",
    "Строка на английском",
    "Упомяни маму",
    "Рифма на ция",
    "Упомяни время 3 утра",
    "Внутренняя рифма везде",
]

# =============================================================================
# GENRE/STYLE PRESETS - Expanded with sub-genres, moods, vibes
# =============================================================================

GENRES = {
    "trap": {
        "name_ru": "ТРЭП",
        "bpm_range": (140, 160),
        "mood": "агрессивно",
        "tags": ["808", "hi-hats", "dark"],
        "color": (255, 50, 100),  # Hot pink
    },
    "drill": {
        "name_ru": "ДРИЛЛ",
        "bpm_range": (140, 145),
        "mood": "жёстко",
        "tags": ["UK drill", "sliding 808", "dark"],
        "color": (100, 100, 255),  # Blue
    },
    "cloud": {
        "name_ru": "КЛАУД",
        "bpm_range": (130, 145),
        "mood": "меланхолично",
        "tags": ["ethereal", "reverb", "sad"],
        "color": (200, 150, 255),  # Lavender
    },
    "boombap": {
        "name_ru": "БУМ-БЭП",
        "bpm_range": (85, 95),
        "mood": "олдскул",
        "tags": ["classic", "sample", "boom bap"],
        "color": (255, 180, 50),  # Gold
    },
    "phonk": {
        "name_ru": "ФОНК",
        "bpm_range": (130, 145),
        "mood": "дерзко",
        "tags": ["Memphis", "cowbell", "drift"],
        "color": (150, 50, 200),  # Purple
    },
    "hyperpop": {
        "name_ru": "ГИПЕРПОП",
        "bpm_range": (150, 180),
        "mood": "хаотично",
        "tags": ["glitchy", "pitched vocals", "maximalist"],
        "color": (255, 100, 255),  # Magenta
    },
    "rage": {
        "name_ru": "РЭЙДЖ",
        "bpm_range": (150, 165),
        "mood": "бешено",
        "tags": ["distorted", "synths", "aggressive"],
        "color": (255, 0, 50),  # Red
    },
    "plugg": {
        "name_ru": "ПЛАГ",
        "bpm_range": (140, 155),
        "mood": "расслабленно",
        "tags": ["flutes", "bells", "spacey"],
        "color": (100, 200, 150),  # Teal
    },
}

# Sub-genres for each main genre
SUB_GENRES = {
    "trap": [
        {"id": "hard_trap", "name_ru": "ХАРД ТРЭП", "desc": "Жёсткие 808, тяжёлые биты"},
        {"id": "melodic_trap", "name_ru": "МЕЛОДИК", "desc": "Мелодичный, эмоциональный"},
        {"id": "dark_trap", "name_ru": "ДАРК ТРЭП", "desc": "Мрачный, атмосферный"},
        {"id": "club_trap", "name_ru": "КЛУБНЫЙ", "desc": "Для танцпола"},
    ],
    "drill": [
        {"id": "uk_drill", "name_ru": "UK ДРИЛЛ", "desc": "Британский стиль"},
        {"id": "ny_drill", "name_ru": "NY ДРИЛЛ", "desc": "Нью-Йорк стиль"},
        {"id": "chicago_drill", "name_ru": "ЧИКАГО", "desc": "Оригинальный дрилл"},
    ],
    "cloud": [
        {"id": "cloud_rap", "name_ru": "КЛАУД РЭП", "desc": "Воздушный, мечтательный"},
        {"id": "emo_cloud", "name_ru": "ЭМО КЛАУД", "desc": "Грустный, эмоциональный"},
        {"id": "witch_house", "name_ru": "ВИЧ ХАУС", "desc": "Тёмный, оккультный"},
    ],
    "boombap": [
        {"id": "classic_boom", "name_ru": "КЛАССИКА", "desc": "90s стиль"},
        {"id": "jazzy_boom", "name_ru": "ДЖАЗИ", "desc": "Джазовые сэмплы"},
        {"id": "hardcore_boom", "name_ru": "ХАРДКОР", "desc": "Жёсткий бумбэп"},
    ],
    "phonk": [
        {"id": "drift_phonk", "name_ru": "ДРИФТ", "desc": "Для тачек и дрифта"},
        {"id": "memphis_phonk", "name_ru": "МЕМФИС", "desc": "Оригинальный стиль"},
        {"id": "house_phonk", "name_ru": "ХАУС ФОНК", "desc": "Танцевальный фонк"},
    ],
    "hyperpop": [
        {"id": "glitch_pop", "name_ru": "ГЛИТЧ", "desc": "Глитчевый, сломанный"},
        {"id": "pc_music", "name_ru": "PC МЬЮЗИК", "desc": "Экспериментальный поп"},
    ],
    "rage": [
        {"id": "rage_beat", "name_ru": "РЭЙДЖ БИТ", "desc": "Классический рэйдж"},
        {"id": "rage_plugg", "name_ru": "РЭЙДЖ ПЛАГ", "desc": "Гибрид стилей"},
    ],
    "plugg": [
        {"id": "plugg_classic", "name_ru": "КЛАССИК ПЛАГ", "desc": "Оригинальный стиль"},
        {"id": "evil_plugg", "name_ru": "ЭВИЛ ПЛАГ", "desc": "Тёмный плаг"},
    ],
}

# Available moods
MOODS = [
    {"id": "aggressive", "name_ru": "АГРЕССИВНО", "emoji": "🔥", "desc": "Жёстко и дерзко"},
    {"id": "melancholic", "name_ru": "МЕЛАНХОЛИЧНО", "emoji": "🌧", "desc": "Грустно и задумчиво"},
    {"id": "romantic", "name_ru": "РОМАНТИЧНО", "emoji": "💕", "desc": "Про любовь и чувства"},
    {"id": "party", "name_ru": "ТУСОВОЧНО", "emoji": "🎉", "desc": "Для вечеринки"},
    {"id": "chill", "name_ru": "РАССЛАБЛЕННО", "emoji": "😌", "desc": "Спокойно и легко"},
    {"id": "dark", "name_ru": "МРАЧНО", "emoji": "🖤", "desc": "Тёмный вайб"},
    {"id": "flex", "name_ru": "ФЛЕКС", "emoji": "💎", "desc": "Про деньги и успех"},
    {"id": "street", "name_ru": "УЛИЦЫ", "emoji": "🏙", "desc": "Уличная история"},
    {"id": "crazy", "name_ru": "БЕЗУМНО", "emoji": "🤪", "desc": "Хаос и угар"},
    {"id": "dreamy", "name_ru": "МЕЧТАТЕЛЬНО", "emoji": "✨", "desc": "Воздушно и лёгко"},
]

# Available vibes (overall atmosphere)
VIBES = [
    {"id": "club", "name_ru": "КЛУБНЫЙ", "desc": "Для танцпола VIP"},
    {"id": "street", "name_ru": "УЛИЧНЫЙ", "desc": "Район, двор, блок"},
    {"id": "night", "name_ru": "НОЧНОЙ", "desc": "После полуночи"},
    {"id": "summer", "name_ru": "ЛЕТНИЙ", "desc": "Жара, пляж, кабрио"},
    {"id": "winter", "name_ru": "ЗИМНИЙ", "desc": "Холод, снег, Питер"},
    {"id": "lounge", "name_ru": "ЛАУНЖ", "desc": "Бар, коктейли, чилл"},
    {"id": "drift", "name_ru": "ДРИФТ", "desc": "Тачки, скорость, гонки"},
    {"id": "game", "name_ru": "ИГРОВОЙ", "desc": "Геймерский вайб"},
    {"id": "workout", "name_ru": "КАЧАЛКА", "desc": "Для тренировки"},
    {"id": "party", "name_ru": "АФТЕПАТИ", "desc": "После клуба, 5 утра"},
    {"id": "romantic", "name_ru": "СВИДАНИЕ", "desc": "Для двоих"},
    {"id": "hustle", "name_ru": "ХАСЛ", "desc": "Работа, деньги, движ"},
]


@dataclass
class WordSelection:
    """A selection of words for track generation."""
    words: List[str]
    joker: Optional[str]
    genre: str
    sub_genre: Optional[str] = None
    mood: Optional[str] = None
    vibe: Optional[str] = None

    def to_prompt(self) -> str:
        """Convert to a prompt string for lyrics generation."""
        words_str = ", ".join(self.words)
        prompt = f"Слова для использования: {words_str}"
        if self.joker:
            prompt += f"\nСпециальное правило: {self.joker}"
        return prompt

    def get_style_prompt(self) -> str:
        """Get the full style description for Suno."""
        parts = []

        # Main genre
        genre_info = GENRES.get(self.genre, GENRES["trap"])
        parts.append(f"russian {self.genre}")

        # Sub-genre if set
        if self.sub_genre:
            sub_genres = SUB_GENRES.get(self.genre, [])
            for sg in sub_genres:
                if sg["id"] == self.sub_genre:
                    parts.append(sg["desc"].lower())
                    break

        # Mood
        if self.mood:
            for m in MOODS:
                if m["id"] == self.mood:
                    parts.append(m["desc"].lower())
                    break

        # Vibe
        if self.vibe:
            for v in VIBES:
                if v["id"] == self.vibe:
                    parts.append(v["desc"].lower())
                    break

        # BPM
        bpm = (genre_info["bpm_range"][0] + genre_info["bpm_range"][1]) // 2
        parts.append(f"{bpm} bpm")

        return ", ".join(parts)


class WordBank:
    """Manager for word selection with anti-repeat logic."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/raptrack")
        self.recent_words: List[str] = []
        self.max_recent = 200
        self._load_recent()

    def _load_recent(self) -> None:
        """Load recent words from file."""
        recent_file = self.data_dir / "recent_words.json"
        if recent_file.exists():
            try:
                with open(recent_file) as f:
                    self.recent_words = json.load(f)
            except Exception:
                self.recent_words = []

    def _save_recent(self) -> None:
        """Save recent words to file."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        recent_file = self.data_dir / "recent_words.json"
        try:
            with open(recent_file, "w") as f:
                json.dump(self.recent_words[-self.max_recent:], f)
        except Exception:
            pass

    def get_random_words(
        self,
        category: str,
        count: int = 3,
        exclude_recent: bool = True
    ) -> List[str]:
        """Get random words from a category, avoiding recent ones."""
        if category not in WORDS:
            category = random.choice(list(WORDS.keys()))

        pool = WORDS[category].copy()

        if exclude_recent:
            pool = [w for w in pool if w not in self.recent_words]
            # If too few left, allow some repeats
            if len(pool) < count:
                pool = WORDS[category].copy()

        selected = random.sample(pool, min(count, len(pool)))
        return selected

    def get_slot_options(self, slot_num: int) -> List[str]:
        """Get 3 word options for a slot (slot machine style).

        Different slots pull from different categories for variety.
        """
        # Rotate through interesting category combos
        category_rotation = [
            ["рэперы", "флекс", "сленг"],
            ["клуб", "эмоции", "действия"],
            ["места", "абсурд", "мета"],
            ["сленг", "абсурд", "эмоции"],
        ]

        cats = category_rotation[slot_num % len(category_rotation)]
        options = []
        for cat in cats:
            words = self.get_random_words(cat, count=1)
            if words:
                options.append(words[0])

        return options

    def get_joker(self) -> str:
        """Get a random joker rule."""
        return random.choice(JOKER_RULES)

    def get_all_jokers(self) -> List[str]:
        """Get all joker rules for slot machine."""
        return JOKER_RULES.copy()

    def get_words_by_category_index(self, index: int, count: int = 20) -> List[str]:
        """Get random words from a category by index.

        Used for slot machine word pools.
        """
        categories = list(WORDS.keys())
        category = categories[index % len(categories)]

        # Get more words than needed, shuffled
        pool = WORDS[category].copy()
        random.shuffle(pool)

        # If we need more, add from other categories
        if len(pool) < count:
            for other_cat in categories:
                if other_cat != category:
                    extra = WORDS[other_cat].copy()
                    random.shuffle(extra)
                    pool.extend(extra[:count - len(pool)])
                    if len(pool) >= count:
                        break

        return pool[:count]

    def record_selection(self, words: List[str]) -> None:
        """Record selected words to avoid repeats."""
        self.recent_words.extend(words)
        self.recent_words = self.recent_words[-self.max_recent:]
        self._save_recent()

    def create_selection(
        self,
        words: List[str],
        include_joker: bool = True,
        genre: str = "trap"
    ) -> WordSelection:
        """Create a word selection for generation."""
        joker = self.get_joker() if include_joker else None
        self.record_selection(words)
        return WordSelection(words=words, joker=joker, genre=genre)


# Quick test
if __name__ == "__main__":
    bank = WordBank()

    print("=== WORD BANK TEST ===\n")

    for i in range(4):
        opts = bank.get_slot_options(i)
        print(f"Slot {i+1}: {opts}")

    print(f"\nJoker: {bank.get_joker()}")

    print("\n=== All categories ===")
    for cat, words in WORDS.items():
        print(f"{cat}: {len(words)} words")
        print(f"  Examples: {random.sample(words, min(5, len(words)))}")
