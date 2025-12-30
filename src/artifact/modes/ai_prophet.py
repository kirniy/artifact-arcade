"""AI Prophet mode - The KEY mode with camera + AI integration.

This is the flagship mode of VNVNC:
1. Camera captures user photo
2. User answers 5 fun binary questions (left/right buttons)
3. AI analyzes photo and answers to generate personalized prediction
4. AI generates a caricature of the user
5. Combined receipt prints with caricature + prediction + date

Uses Gemini 2.5 Flash for predictions and Imagen 3 for caricatures.
"""

import asyncio
import logging
from typing import Optional, List, Tuple
from datetime import datetime
import random
import math
import numpy as np

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.timeline import Timeline
from artifact.animation.easing import Easing
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.ai.predictor import PredictionService, Prediction, PredictionCategory
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.audio.engine import get_audio_engine
from artifact.utils.camera import create_viewfinder_overlay
from artifact.utils.camera_service import camera_service
from artifact.utils.s3_upload import AsyncUploader, UploadResult
from artifact.animation.santa_runner import SantaRunner

logger = logging.getLogger(__name__)


class ProphetPhase:
    """Sub-phases within the AI Prophet mode."""

    INTRO = "intro"              # Welcome animation
    CAMERA_PREP = "camera_prep"  # "Look at camera" prompt
    CAMERA_CAPTURE = "capture"   # Capturing photo
    QUESTIONS = "questions"      # Binary questions
    PROCESSING = "processing"    # AI generation (parallel)
    REVEAL = "reveal"            # Dramatic reveal
    RESULT = "result"            # Final display


# =============================================================================
# FUN GEN-Z RUSSIAN QUESTIONS DATABASE
# =============================================================================
# Each question is (text, trait_key, left_label, right_label, left_meaning, right_meaning)
# - left_label/right_label: What to show on buttons (SHORT - max 6 chars!)
# - left_meaning/right_meaning: What choosing that option means for AI context

QUESTIONS_DATABASE: List[Tuple[str, str, str, str, str, str]] = [
    # ==========================================================================
    # DIGITAL LIFE & СОЦИАЛКИ (20 questions)
    # ==========================================================================
    ("Скроллишь рилсы перед сном?", "digital", "НЕТ", "ДА", "здоровый сон", "залипает в телефон"),
    ("Постишь сторис каждый день?", "social_media", "НЕТ", "ДА", "скромный", "контент-мейкер"),
    ("Читаешь комменты под постами?", "curious", "НЕТ", "ДА", "пофигист", "любопытный"),
    ("Сталкеришь экс в соцсетях?", "obsessive", "НЕТ", "ДА", "отпустил", "не отпускает"),
    ("Удаляешь неудачные фото?", "perfectionist", "НЕТ", "ДА", "пофиг на вид", "перфекционист"),
    ("Отвечаешь на сообщения сразу?", "responsive", "НЕТ", "ДА", "игнорит", "отвечает мгновенно"),
    ("Гуглишь симптомы болезней?", "anxious", "НЕТ", "ДА", "спокойный", "ипохондрик"),
    ("Слушаешь подкасты?", "intellectual", "НЕТ", "ДА", "визуал", "аудиал"),
    ("Смотришь тикток на скорости 2x?", "impatient", "НЕТ", "ДА", "терпеливый", "нетерпеливый"),
    ("Шеришь мемы в чаты?", "social", "НЕТ", "ДА", "молчун", "душа компании"),
    ("Записываешь голосовые?", "expressive", "НЕТ", "ДА", "текстовик", "голосовушник"),
    ("Юзаешь темную тему везде?", "aesthetic", "НЕТ", "ДА", "светлая сторона", "темная сторона"),
    ("Подписан на 500+ человек?", "fomo", "НЕТ", "ДА", "минималист", "коллекционер"),
    ("Чекаешь телефон первым делом?", "addicted", "НЕТ", "ДА", "осознанный", "зависимый"),
    ("Фоткаешь еду?", "aesthetic_food", "НЕТ", "ДА", "просто ест", "инста-фудблогер"),
    ("Ставишь таймер на соцсети?", "disciplined", "НЕТ", "ДА", "без границ", "дисциплина"),
    ("Смотришь сторис инкогнито?", "sneaky", "НЕТ", "ДА", "открытый", "шпион"),
    ("Есть finsta/закрытый акк?", "private", "НЕТ", "ДА", "публичный", "приватный"),
    ("Читаешь книги с телефона?", "digital_reader", "НЕТ", "ДА", "бумажный", "цифровой"),
    ("Донатишь стримерам?", "generous", "НЕТ", "ДА", "экономный", "щедрый"),

    # ==========================================================================
    # ОТНОШЕНИЯ & ЛЮБОВЬ (25 questions)
    # ==========================================================================
    ("Первым пишешь крашу?", "confident", "НЕТ", "ДА", "стесняшка", "уверенный"),
    ("Веришь в любовь с первого взгляда?", "romantic", "НЕТ", "ДА", "реалист", "романтик"),
    ("Ревнуешь?", "jealous", "НЕТ", "ДА", "доверяет", "ревнивец"),
    ("Флиртуешь неосознанно?", "flirty", "НЕТ", "ДА", "серьезный", "флиртун"),
    ("Веришь в родственные души?", "soulmate", "НЕТ", "ДА", "скептик", "верит в судьбу"),
    ("Прощаешь измену?", "forgiving_love", "НЕТ", "ДА", "категоричный", "всепрощающий"),
    ("Говоришь я люблю тебя первым?", "vulnerable", "НЕТ", "ДА", "закрытый", "открытый"),
    ("Помнишь годовщины?", "attentive", "НЕТ", "ДА", "забывчивый", "внимательный"),
    ("Знакомишь с родителями быстро?", "serious", "НЕТ", "ДА", "осторожный", "серьезный"),
    ("Веришь в дружбу м/ж?", "platonic", "НЕТ", "ДА", "не верит", "верит"),
    ("Можешь простить предательство?", "forgiving", "НЕТ", "ДА", "злопамятный", "прощает"),
    ("Говоришь о чувствах?", "emotional_open", "НЕТ", "ДА", "скрытный", "открытый"),
    ("Даришь подарки без повода?", "spontaneous_love", "НЕТ", "ДА", "практичный", "романтик"),
    ("Пишешь длинные сообщения?", "expressive_text", "НЕТ", "ДА", "краткий", "развернутый"),
    ("Веришь в любовь на расстоянии?", "distant_love", "НЕТ", "ДА", "реалист", "верит"),
    ("Ждешь первого шага?", "passive_love", "НЕТ", "ДА", "инициатор", "ждет"),
    ("Влюбляешься быстро?", "fast_love", "НЕТ", "ДА", "медленно", "с первого взгляда"),
    ("Остаешься друзьями с экс?", "mature", "НЕТ", "ДА", "режет связи", "зрелый"),
    ("Любишь обнимашки?", "physical", "НЕТ", "ДА", "личное пространство", "тактильный"),
    ("Делаешь сюрпризы?", "surprise", "НЕТ", "ДА", "предсказуемый", "сюрпризер"),
    ("Запоминаешь мелочи о людях?", "observant", "НЕТ", "ДА", "рассеянный", "внимательный"),
    ("Ссоришься громко?", "confrontational", "НЕТ", "ДА", "молчит", "выясняет"),
    ("Миришься первым?", "peacemaker", "НЕТ", "ДА", "гордый", "миротворец"),
    ("Веришь во вторые шансы?", "hopeful", "НЕТ", "ДА", "однозначный", "дает шансы"),
    ("Любовь или карьера?", "priority", "КАРЬЕРА", "ЛЮБОВЬ", "карьерист", "романтик"),

    # ==========================================================================
    # ХАРАКТЕР & ЛИЧНОСТЬ (30 questions)
    # ==========================================================================
    ("Опаздываешь всегда?", "punctual", "НЕТ", "ДА", "пунктуальный", "вечно опаздывает"),
    ("Споришь до победного?", "stubborn", "НЕТ", "ДА", "уступчивый", "упертый"),
    ("Плачешь от фильмов?", "emotional", "НЕТ", "ДА", "железный", "эмоциональный"),
    ("Веришь в себя?", "self_confident", "НЕТ", "ДА", "сомневается", "уверен"),
    ("Легко просишь помощь?", "independent", "НЕТ", "ДА", "сам справлюсь", "просит"),
    ("Держишь обиду долго?", "grudge", "НЕТ", "ДА", "отпускает", "помнит все"),
    ("Любишь быть в центре?", "attention", "НЕТ", "ДА", "тень", "звезда"),
    ("Делаешь что хочешь?", "free_spirit", "НЕТ", "ДА", "по правилам", "свободный"),
    ("Говоришь правду в лицо?", "honest", "НЕТ", "ДА", "дипломат", "прямой"),
    ("Рискуешь?", "risk_taker", "НЕТ", "ДА", "осторожный", "рисковый"),
    ("Принимаешь решения быстро?", "decisive", "НЕТ", "ДА", "думает долго", "решительный"),
    ("Соврешь ради друга?", "protective", "НЕТ", "ДА", "честный", "защитник"),
    ("Признаешь ошибки?", "humble", "НЕТ", "ДА", "упертый", "признает"),
    ("Завидуешь?", "envious", "НЕТ", "ДА", "довольный", "завистливый"),
    ("Сплетничаешь?", "gossip", "НЕТ", "ДА", "молчит", "разносит чай"),
    ("Доверяешь интуиции?", "intuitive", "НЕТ", "ДА", "логик", "интуит"),
    ("Конкурентный?", "competitive", "НЕТ", "ДА", "пофигист", "хочет побеждать"),
    ("Перфекционист?", "perfectionist", "НЕТ", "ДА", "и так сойдет", "идеалист"),
    ("Прокрастинируешь?", "procrastinator", "НЕТ", "ДА", "делает сразу", "откладывает"),
    ("Многозадачный?", "multitasker", "НЕТ", "ДА", "одно дело", "жонглер задач"),
    ("Любишь рутину?", "routine", "НЕТ", "ДА", "хаос", "порядок"),
    ("Сарказм — твой язык?", "sarcastic", "НЕТ", "ДА", "серьезный", "саркастичный"),
    ("Легко смеешься?", "joyful", "НЕТ", "ДА", "серьезный", "хохотушка"),
    ("Контролфрик?", "control", "НЕТ", "ДА", "пофигист", "контролирует все"),
    ("Запоминаешь имена?", "memory", "НЕТ", "ДА", "забывает", "помнит"),
    ("Любишь учиться?", "curious_learn", "НЕТ", "ДА", "хватит школы", "вечный студент"),
    ("Экстраверт?", "extrovert", "НЕТ", "ДА", "интроверт", "экстраверт"),
    ("Оптимист?", "optimist", "НЕТ", "ДА", "пессимист", "оптимист"),
    ("Терпеливый?", "patient", "НЕТ", "ДА", "нетерпеливый", "терпеливый"),
    ("Амбициозный?", "ambitious", "НЕТ", "ДА", "спокойный", "амбициозный"),

    # ==========================================================================
    # ЛАЙФСТАЙЛ & ПРИВЫЧКИ (25 questions)
    # ==========================================================================
    ("Пьешь кофе каждый день?", "coffee", "НЕТ", "ДА", "чайный", "кофеман"),
    ("Занимаешься спортом?", "fitness", "НЕТ", "ДА", "лежачий", "качок"),
    ("Ешь после полуночи?", "night_eater", "НЕТ", "ДА", "режим", "ночной жор"),
    ("Просыпаешься по будильнику?", "alarm", "НЕТ", "ДА", "естественно", "по звонку"),
    ("Спишь с телефоном рядом?", "phone_sleeper", "НЕТ", "ДА", "откладывает", "всегда рядом"),
    ("Делаешь зарядку?", "morning_person", "НЕТ", "ДА", "сова", "жаворонок"),
    ("Готовишь сам?", "cook", "НЕТ", "ДА", "доставка", "шеф-повар"),
    ("Тратишь на шмот много?", "fashion", "НЕТ", "ДА", "экономный", "шопоголик"),
    ("Копишь деньги?", "saver", "НЕТ", "ДА", "транжира", "копилка"),
    ("Планируешь бюджет?", "budget", "НЕТ", "ДА", "как пойдет", "планировщик"),
    ("Пьешь алкоголь?", "alcohol", "НЕТ", "ДА", "трезвенник", "выпивает"),
    ("Куришь?", "smoker", "НЕТ", "ДА", "чистые легкие", "курильщик"),
    ("Ложишься до полуночи?", "early_sleeper", "НЕТ", "ДА", "сова", "ранняя пташка"),
    ("Принимаешь витамины?", "health", "НЕТ", "ДА", "естественный", "биохакер"),
    ("Медитируешь?", "mindful", "НЕТ", "ДА", "хаотичный ум", "дзен"),
    ("Читаешь книги?", "reader", "НЕТ", "ДА", "нечитающий", "книжный червь"),
    ("Слушаешь музыку постоянно?", "music", "НЕТ", "ДА", "тишина", "меломан"),
    ("Играешь в видеоигры?", "gamer", "НЕТ", "ДА", "не геймер", "геймер"),
    ("Смотришь сериалы запоем?", "binger", "НЕТ", "ДА", "по серии", "запойный"),
    ("Убираешься регулярно?", "clean", "НЕТ", "ДА", "хаос", "чистюля"),
    ("Выбрасываешь старые вещи?", "minimalist", "НЕТ", "ДА", "хранит все", "минималист"),
    ("Ходишь пешком много?", "walker", "НЕТ", "ДА", "транспорт", "пешеход"),
    ("Веган/вегетарианец?", "diet", "НЕТ", "ДА", "мясоед", "растительный"),
    ("Пьешь воду 2л в день?", "hydrated", "НЕТ", "ДА", "обезвоженный", "водохлеб"),
    ("Ведешь дневник/заметки?", "journaler", "НЕТ", "ДА", "в голове", "записывает"),

    # ==========================================================================
    # СОЦИУМ & ДРУЗЬЯ (20 questions)
    # ==========================================================================
    ("Легко заводишь друзей?", "friendly", "НЕТ", "ДА", "закрытый", "открытый"),
    ("Есть лучший друг?", "bestie", "НЕТ", "ДА", "много равных", "есть бестик"),
    ("Делишься проблемами?", "sharing", "НЕТ", "ДА", "все в себе", "открытый"),
    ("Легко говоришь с незнакомцами?", "social", "НЕТ", "ДА", "молчит", "общительный"),
    ("Организуешь встречи?", "organizer", "НЕТ", "ДА", "ждет приглашения", "организатор"),
    ("Приходишь на все тусы?", "party", "НЕТ", "ДА", "домосед", "тусовщик"),
    ("Поддерживаешь связь с детскими друзьями?", "loyal_friend", "НЕТ", "ДА", "новые связи", "верный"),
    ("Помогаешь без просьбы?", "helpful", "НЕТ", "ДА", "ждет просьбы", "инициативный"),
    ("Сплетничаешь с друзьями?", "gossiper", "НЕТ", "ДА", "молчит", "обсуждает"),
    ("Можешь быть один долго?", "loner", "НЕТ", "ДА", "нужны люди", "одиночка"),
    ("Знакомишь друзей между собой?", "connector", "НЕТ", "ДА", "разделяет круги", "связующий"),
    ("Даешь деньги в долг?", "lending", "НЕТ", "ДА", "не дает", "выручает"),
    ("Помнишь дни рождения?", "remembers_bd", "НЕТ", "ДА", "забывает", "помнит"),
    ("Звонишь или пишешь?", "communication", "ПИШУ", "ЗВОНЮ", "текстер", "звонящий"),
    ("Ценишь качество или количество друзей?", "friends_value", "МНОГО", "МАЛО", "экстраверт", "избирательный"),
    ("Прощаешь друзей легко?", "forgiving_friend", "НЕТ", "ДА", "строгий", "прощающий"),
    ("Делишь друзей на близких/обычных?", "friend_tiers", "НЕТ", "ДА", "все равны", "иерархия"),
    ("Друзья знают твои секреты?", "secrets", "НЕТ", "ДА", "закрытый", "открытый"),
    ("Познакомишь друга с работой?", "connector_work", "НЕТ", "ДА", "разделяет", "смешивает"),
    ("Дружишь с коллегами?", "work_friends", "НЕТ", "ДА", "только работа", "дружит"),

    # ==========================================================================
    # ФИЛОСОФИЯ & ГЛУБОКИЕ ВОПРОСЫ (20 questions)
    # ==========================================================================
    ("Веришь в судьбу?", "fate", "НЕТ", "ДА", "сам строит жизнь", "фаталист"),
    ("Веришь в карму?", "karma", "НЕТ", "ДА", "не верит", "кармический"),
    ("Веришь в загробную жизнь?", "afterlife", "НЕТ", "ДА", "материалист", "верит"),
    ("Веришь в знаки вселенной?", "signs", "НЕТ", "ДА", "рационалист", "мистик"),
    ("Веришь в гороскопы?", "astrology", "НЕТ", "ДА", "скептик", "астролог"),
    ("Все к лучшему?", "optimistic_fate", "НЕТ", "ДА", "пессимист", "оптимист"),
    ("Жизнь имеет смысл?", "meaning", "НЕТ", "ДА", "нигилист", "верит в смысл"),
    ("Боишься смерти?", "death_fear", "НЕТ", "ДА", "спокоен", "боится"),
    ("Изменил бы прошлое?", "regrets", "НЕТ", "ДА", "принимает", "жалеет"),
    ("Люди добрые по природе?", "human_nature", "НЕТ", "ДА", "циник", "верит в добро"),
    ("Цель оправдывает средства?", "ethics", "НЕТ", "ДА", "этичный", "прагматик"),
    ("Важнее путь или цель?", "journey", "ЦЕЛЬ", "ПУТЬ", "результатник", "процессник"),
    ("Живешь моментом?", "present", "НЕТ", "ДА", "планировщик", "здесь и сейчас"),
    ("Думаешь о будущем часто?", "future", "НЕТ", "ДА", "в моменте", "планирует"),
    ("Сожалеешь о решениях?", "regret", "НЕТ", "ДА", "принимает", "сожалеет"),
    ("Деньги = счастье?", "money_happy", "НЕТ", "ДА", "не в деньгах", "материалист"),
    ("Свобода важнее безопасности?", "freedom", "НЕТ", "ДА", "стабильность", "свобода"),
    ("Успех = деньги?", "success_money", "НЕТ", "ДА", "не в деньгах", "да, бабки"),
    ("Можно ли изменить мир?", "change_world", "НЕТ", "ДА", "реалист", "мечтатель"),
    ("Одиночество пугает?", "loneliness", "НЕТ", "ДА", "комфортен один", "боится"),

    # ==========================================================================
    # РАЗВЛЕЧЕНИЯ & ИНТЕРЕСЫ (20 questions)
    # ==========================================================================
    ("Пицца с ананасами?", "pineapple", "ФУ", "ДА", "традиционалист", "экспериментатор"),
    ("Кошки или собаки?", "pet", "КОШКИ", "СОБАКИ", "кошатник", "собачник"),
    ("Горы или море?", "vacation", "ГОРЫ", "МОРЕ", "горный", "морской"),
    ("Утро или вечер?", "time", "УТРО", "ВЕЧЕР", "жаворонок", "сова"),
    ("Лето или зима?", "season", "ЛЕТО", "ЗИМА", "летний", "зимний"),
    ("Сладкое или соленое?", "taste", "СЛАДКОЕ", "СОЛЕНОЕ", "сладкоежка", "соленый"),
    ("Фильмы или сериалы?", "watch", "ФИЛЬМЫ", "СЕРИАЛЫ", "кинолюб", "сериальщик"),
    ("Книги или кино?", "media", "КНИГИ", "КИНО", "читатель", "зритель"),
    ("Дома или тусовки?", "social_pref", "ДОМА", "ТУСЫ", "домосед", "тусовщик"),
    ("Город или природа?", "environment", "ГОРОД", "ПРИРОДА", "урбанист", "натуралист"),
    ("Спорт или искусство?", "activity", "СПОРТ", "АРТ", "спортсмен", "художник"),
    ("Логика или интуиция?", "thinking", "ЛОГИКА", "ИНТУИЦИЯ", "логик", "интуит"),
    ("Один или в команде?", "work_style", "ОДИН", "КОМАНДА", "одиночка", "командный"),
    ("Планы или спонтанность?", "planning", "ПЛАНЫ", "СПОНТАН", "планер", "спонтанный"),
    ("Тишина или музыка?", "sound", "ТИШИНА", "МУЗЫКА", "тихоня", "музыкальный"),
    ("Чай или кофе?", "drink", "ЧАЙ", "КОФЕ", "чайник", "кофейник"),
    ("Пиво или вино?", "alcohol_pref", "ПИВО", "ВИНО", "пивной", "винный"),
    ("Суши или пицца?", "food", "СУШИ", "ПИЦЦА", "японофил", "итальянщик"),
    ("Netflix или YouTube?", "platform", "NETFLIX", "YOUTUBE", "нетфликсер", "ютубер"),
    ("Android или iPhone?", "phone", "ANDROID", "IPHONE", "андроид", "яблочник"),

    # ==========================================================================
    # РАБОТА & АМБИЦИИ (15 questions)
    # ==========================================================================
    ("Мечтаешь о своем бизнесе?", "entrepreneur", "НЕТ", "ДА", "сотрудник", "предприниматель"),
    ("Работаешь на выходных?", "workaholic", "НЕТ", "ДА", "отдыхает", "трудоголик"),
    ("Деньги или призвание?", "motivation", "ДЕНЬГИ", "ПРИЗВАНИЕ", "практик", "идеалист"),
    ("Хочешь стать боссом?", "leadership", "НЕТ", "ДА", "исполнитель", "лидер"),
    ("Важен офис или удаленка?", "workplace", "ОФИС", "УДАЛЕНКА", "офисный", "свободный"),
    ("Готов переехать ради работы?", "mobile", "НЕТ", "ДА", "оседлый", "мобильный"),
    ("Стабильность или риск?", "career_risk", "СТАБИЛЬНОСТЬ", "РИСК", "стабильный", "рисковый"),
    ("Пойдешь по головам?", "ruthless", "НЕТ", "ДА", "этичный", "безжалостный"),
    ("Важен статус?", "status", "НЕТ", "ДА", "скромный", "статусный"),
    ("Работа = жизнь?", "worklife", "НЕТ", "ДА", "баланс", "карьерист"),
    ("Учишься новому на работе?", "growth", "НЕТ", "ДА", "застой", "растет"),
    ("Нравится твоя работа?", "job_satisfaction", "НЕТ", "ДА", "терпит", "любит"),
    ("Хочешь славы?", "fame", "НЕТ", "ДА", "скромный", "хочет известности"),
    ("Завидуешь успешным?", "success_envy", "НЕТ", "ДА", "вдохновляется", "завидует"),
    ("Что важнее?", "priority_work", "УСПЕХ", "ПОКОЙ", "карьерист", "пофигист"),

    # ==========================================================================
    # РАНДОМ & ВАЙБЫ (25 questions)
    # ==========================================================================
    ("Пойдешь на тусу без инвайта?", "bold", "НЕТ", "ДА", "скромный", "дерзкий"),
    ("Можешь уехать спонтанно?", "spontaneous", "НЕТ", "ДА", "планировщик", "спонтанный"),
    ("Танцуешь на публике?", "dancer", "НЕТ", "ДА", "стесняется", "отрывается"),
    ("Поешь в душе?", "shower_singer", "НЕТ", "ДА", "молчит", "солист"),
    ("Разговариваешь сам с собой?", "self_talk", "НЕТ", "ДА", "молчит", "философ"),
    ("Плачешь при людях?", "public_emotion", "НЕТ", "ДА", "скрывает", "открытый"),
    ("Смеешься над своими шутками?", "self_laugh", "НЕТ", "ДА", "серьезный", "хохотун"),
    ("Веришь в НЛО?", "aliens", "НЕТ", "ДА", "скептик", "верит"),
    ("Боишься пауков?", "spiders", "НЕТ", "ДА", "храбрый", "арахнофоб"),
    ("Снятся кошмары?", "nightmares", "НЕТ", "ДА", "спит спокойно", "кошмарит"),
    ("Помнишь сны?", "dreams", "НЕТ", "ДА", "не помнит", "помнит"),
    ("Веришь в призраков?", "ghosts", "НЕТ", "ДА", "скептик", "мистик"),
    ("Суеверный?", "superstitious", "НЕТ", "ДА", "рационалист", "суеверный"),
    ("Носишь талисман?", "talisman", "НЕТ", "ДА", "не носит", "носит"),
    ("Загадываешь желание на 11:11?", "wishes", "НЕТ", "ДА", "не верит", "загадывает"),
    ("Веришь в приметы?", "omens", "НЕТ", "ДА", "игнорит", "следит"),
    ("Открываешь окно зимой?", "cold_lover", "НЕТ", "ДА", "мерзляк", "морж"),
    ("Ешь в постели?", "bed_eater", "НЕТ", "ДА", "нет крошек", "да"),
    ("Моешь посуду сразу?", "dishes", "НЕТ", "ДА", "потом", "сразу"),
    ("Заправляешь кровать?", "bed_maker", "НЕТ", "ДА", "не заправляет", "заправляет"),
    ("Опаздываешь часто?", "late", "НЕТ", "ДА", "пунктуальный", "опаздун"),
    ("Теряешь вещи?", "loser", "НЕТ", "ДА", "организованный", "растеряша"),
    ("Забываешь имена?", "names", "НЕТ", "ДА", "помнит", "забывает"),
    ("Ешь последний кусок?", "last_piece", "НЕТ", "ДА", "оставляет", "забирает"),
    ("Признаешь что не прав?", "admit_wrong", "НЕТ", "ДА", "упрямый", "признает"),
]

# Number of questions to ask per session
QUESTIONS_PER_SESSION = 10


def get_random_questions(count: int = QUESTIONS_PER_SESSION) -> List[Tuple[str, str, str, str, str, str]]:
    """Get random questions from the database.

    Args:
        count: Number of questions to select

    Returns:
        List of (question, trait_key, left_label, right_label, left_meaning, right_meaning) tuples
    """
    # Use a fresh Random instance seeded with high-precision time + random bytes
    # This ensures truly random questions each session, not affected by global state
    import time
    import os
    rng = random.Random()
    # Seed with nanoseconds + random bytes for maximum entropy
    seed = int(time.time() * 1_000_000) ^ int.from_bytes(os.urandom(4), 'big')
    rng.seed(seed)
    questions = rng.sample(QUESTIONS_DATABASE, min(count, len(QUESTIONS_DATABASE)))
    logger.debug(f"Selected {len(questions)} questions from pool of {len(QUESTIONS_DATABASE)}")
    return questions


class AIProphetMode(BaseMode):
    """AI Prophet - Personalized AI fortune telling.

    The signature mode of VNVNC that combines:
    - Live camera capture
    - Personality profiling via 10 fun Gen-Z questions
    - AI-powered prediction generation
    - AI-generated caricature
    - Combined thermal receipt printing

    Flow:
    1. INTRO: Mystical welcome animation
    2. CAMERA_PREP: "Look at the camera" prompt
    3. CAMERA_CAPTURE: Take photo with countdown
    4. QUESTIONS: 10 binary questions (left=no, right=yes)
    5. PROCESSING: AI generates prediction + caricature (parallel)
    6. REVEAL: Dramatic reveal animation
    7. RESULT: Display prediction, offer print
    """

    name = "ai_prophet"
    display_name = "ОРАКУЛ"
    description = "ИИ предсказание судьбы"
    icon = "@"
    style = "modern"
    requires_camera = True
    requires_ai = True
    estimated_duration = 90  # Longer for 5 questions

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Services
        self._prediction_service = PredictionService()
        self._caricature_service = CaricatureService()
        self._audio = get_audio_engine()

        # Sub-phase tracking
        self._sub_phase = ProphetPhase.INTRO

        # Camera state
        self._camera: Optional[SimulatorCamera] = None
        self._camera_frame: Optional[bytes] = None  # Current live frame (dithered)
        self._photo_data: Optional[bytes] = None    # Captured JPEG for AI
        self._camera_countdown: float = 0.0
        self._last_countdown_tick: int = 0  # Track countdown ticks for sound
        self._flash_alpha: float = 0.0

        # Questions state - randomized from database
        self._questions: List[Tuple[str, str, str, str]] = []
        self._current_question: int = 0
        self._answers: List[bool] = []
        self._answer_meanings: List[str] = []  # Store what each answer means
        self._answer_animation: float = 0.0

        # AI results
        self._prediction: Optional[Prediction] = None
        self._caricature: Optional[Caricature] = None
        self._ai_task: Optional[asyncio.Task] = None
        self._processing_progress: float = 0.0
        self._progress_tracker = SmartProgressTracker(mode_theme="ai_prophet")

        # Animation state
        self._reveal_progress: float = 0.0
        self._glow_phase: float = 0.0
        self._scan_line: float = 0.0

        # Result view state - PAGE-BASED navigation (no scrolling!)
        # Flow: Page 0 = first text page, Pages 1-N = more text, then image, then QR
        self._current_page: int = 0
        self._text_pages: List[List[str]] = []  # Lines per text page
        self._total_pages: int = 0
        self._lines_per_page: int = 5  # Lines at scale 2 that fit on screen

        # Particles
        self._particles = ParticleSystem()

        # Colors (modern/tech style)
        self._primary = (59, 130, 246)    # Blue
        self._secondary = (139, 92, 246)   # Purple
        self._accent = (16, 185, 129)      # Teal

        # S3 upload for QR sharing
        self._uploader = AsyncUploader()
        self._qr_url: Optional[str] = None
        self._qr_image: Optional[np.ndarray] = None

        # Santa runner minigame for waiting screen
        self._santa_runner: Optional[SantaRunner] = None

    @property
    def is_ai_available(self) -> bool:
        """Check if AI services are available."""
        return (
            self._prediction_service.is_available or
            self._caricature_service.is_available
        )

    def on_enter(self) -> None:
        """Initialize AI Prophet mode."""
        self._sub_phase = ProphetPhase.INTRO
        self._photo_data = None
        self._camera_frame = None
        self._current_question = 0
        self._answers = []
        self._prediction = None
        self._caricature = None
        self._ai_task = None
        self._processing_progress = 0.0
        self._progress_tracker.reset()
        self._reveal_progress = 0.0

        # Reset pagination state
        self._current_page = 0
        self._text_pages = []
        self._total_pages = 0

        # Reset QR upload state
        self._qr_url = None
        self._qr_image = None

        # Use shared camera service (always running)
        self._camera = camera_service.is_running
        if self._camera:
            logger.info("Camera service ready for AI Prophet mode")
        else:
            logger.warning("Could not open camera, using placeholder")

        # Reset prediction service
        self._prediction_service.reset_profile()

        # Get randomized questions for this session
        self._questions = get_random_questions(QUESTIONS_PER_SESSION)
        self._answers = []
        self._answer_meanings = []
        logger.info(f"Selected {len(self._questions)} random questions for session")

        # Setup particles (tech style)
        magic_config = ParticlePresets.magic(x=64, y=64)
        magic_config.color = self._secondary
        self._particles.add_emitter("magic", magic_config)

        spark_config = ParticlePresets.sparkle(x=64, y=64)
        spark_config.color = self._accent
        self._particles.add_emitter("sparks", spark_config)

        self.change_phase(ModePhase.INTRO)
        logger.info("AI Prophet mode entered")

    def on_update(self, delta_ms: float) -> None:
        """Update AI Prophet mode."""
        self._particles.update(delta_ms)

        # Animation updates
        self._glow_phase += delta_ms * 0.003
        self._scan_line = (self._scan_line + delta_ms * 0.1) % 128

        # Update live camera preview during camera phases
        if self._sub_phase in (ProphetPhase.CAMERA_PREP, ProphetPhase.CAMERA_CAPTURE):
            self._update_camera_preview()

        if self.phase == ModePhase.INTRO:
            if self._sub_phase == ProphetPhase.INTRO:
                # Intro lasts 2.5 seconds
                if self._time_in_phase > 2500:
                    self._sub_phase = ProphetPhase.CAMERA_PREP
                    self._time_in_phase = 0

            elif self._sub_phase == ProphetPhase.CAMERA_PREP:
                # Camera prep for 2 seconds, then start capture
                if self._time_in_phase > 2000:
                    self._start_camera_capture()

            elif self._sub_phase == ProphetPhase.CAMERA_CAPTURE:
                # Countdown animation
                self._camera_countdown = max(0, 3.0 - self._time_in_phase / 1000)

                # Play countdown tick sounds (3, 2, 1)
                current_tick = int(self._camera_countdown) + 1
                if current_tick != self._last_countdown_tick and current_tick >= 1 and current_tick <= 3:
                    self._audio.play_countdown_tick()
                    self._last_countdown_tick = current_tick

                # Capture the photo when countdown reaches 0
                if self._camera_countdown <= 0 and self._photo_data is None:
                    self._do_camera_capture()
                    self._audio.play_camera_shutter()  # Shutter sound
                    self._flash_alpha = 1.0  # Flash!

                # Flash effect after capture
                if self._time_in_phase > 3000:
                    self._flash_alpha = max(0, 1.0 - (self._time_in_phase - 3000) / 500)

                    if self._time_in_phase > 3500:
                        self._start_questions()

        elif self.phase == ModePhase.ACTIVE:
            # Questions phase
            if self._sub_phase == ProphetPhase.QUESTIONS:
                # Answer animation decay
                self._answer_animation = max(0, self._answer_animation - delta_ms / 300)

        elif self.phase == ModePhase.PROCESSING:
            # Update smart progress tracker
            self._progress_tracker.update(delta_ms)

            # Update Santa runner minigame
            if self._santa_runner:
                self._santa_runner.update(delta_ms)

            # Check AI task progress
            if self._ai_task:
                if self._ai_task.done():
                    self._on_ai_complete()
                else:
                    # Use smart progress tracker for visual feedback
                    self._processing_progress = self._progress_tracker.get_progress()

            # Scan line animation
            self._scan_line = (self._time_in_phase / 20) % 128

        elif self.phase == ModePhase.RESULT:
            if self._sub_phase == ProphetPhase.REVEAL:
                self._reveal_progress = min(1.0, self._time_in_phase / 2000)

                if self._reveal_progress >= 1.0:
                    self._sub_phase = ProphetPhase.RESULT
                    # Paginate prediction text when entering result phase
                    if self._prediction and not self._text_pages:
                        self._paginate_prediction()
                    self._current_page = 0  # Start at first text page

            elif self._sub_phase == ProphetPhase.RESULT:
                # NO TIMEOUT - user controls when to exit via button press or BACK
                # User navigates pages with LEFT/RIGHT buttons
                pass

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if event.type == EventType.BUTTON_PRESS:
            if self._sub_phase == ProphetPhase.PROCESSING:
                # Play Santa runner minigame while waiting - JUMP!
                if self._santa_runner:
                    self._santa_runner.handle_jump()
                    self._audio.play_ui_click()
                return True
            elif self.phase == ModePhase.RESULT and self._sub_phase == ProphetPhase.RESULT:
                # Main button = print and finish
                self._finish()
                return True

        elif event.type == EventType.ARCADE_LEFT:
            if self.phase == ModePhase.ACTIVE and self._sub_phase == ProphetPhase.QUESTIONS:
                self._answer_question(False)  # No
                self._audio.play_ui_click()
                return True
            # Previous page in result phase
            if self.phase == ModePhase.RESULT and self._sub_phase == ProphetPhase.RESULT:
                if self._current_page > 0:
                    self._current_page -= 1
                    self._audio.play_ui_move()
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self.phase == ModePhase.ACTIVE and self._sub_phase == ProphetPhase.QUESTIONS:
                self._answer_question(True)  # Yes
                self._audio.play_ui_click()
                return True
            # Next page in result phase
            if self.phase == ModePhase.RESULT and self._sub_phase == ProphetPhase.RESULT:
                if self._current_page < self._total_pages - 1:
                    self._current_page += 1
                    self._audio.play_ui_move()
                return True

        return False

    def _start_camera_capture(self) -> None:
        """Start the camera capture sequence."""
        self._sub_phase = ProphetPhase.CAMERA_CAPTURE
        self._time_in_phase = 0
        self._camera_countdown = 3.0
        logger.info("Camera capture started - countdown begins")

    def _do_camera_capture(self) -> None:
        """Capture photo from shared camera service."""
        self._photo_data = camera_service.capture_jpeg(quality=90)
        if self._photo_data:
            logger.info(f"Captured photo: {len(self._photo_data)} bytes")
        else:
            logger.warning("Failed to capture photo")

    def _update_camera_preview(self) -> None:
        """Update the live camera preview frame - clean B&W grayscale (no dithering)."""
        try:
            frame = camera_service.get_frame(timeout=0)
            if frame is not None and frame.size > 0:
                # Simple B&W grayscale conversion - cleaner than dithering
                if len(frame.shape) == 3:
                    gray = (0.299 * frame[:, :, 0] + 0.587 * frame[:, :, 1] + 0.114 * frame[:, :, 2]).astype(np.uint8)
                else:
                    gray = frame
                # Resize if needed
                if gray.shape != (128, 128):
                    from PIL import Image
                    img = Image.fromarray(gray)
                    img = img.resize((128, 128), Image.Resampling.BILINEAR)
                    gray = np.array(img, dtype=np.uint8)
                # Convert to RGB (grayscale in all 3 channels)
                bw_frame = np.stack([gray, gray, gray], axis=-1)
                self._camera_frame = create_viewfinder_overlay(bw_frame, self._time_in_phase).copy()
                self._camera = True
        except Exception as e:
            logger.warning(f"Camera preview update error: {e}")

    def _start_questions(self) -> None:
        """Start the binary questions sequence."""
        self._sub_phase = ProphetPhase.QUESTIONS
        self._current_question = 0
        self._answers = []
        self.change_phase(ModePhase.ACTIVE)

        logger.info("Questions phase started")

    def _answer_question(self, answer: bool) -> None:
        """Record answer and advance to next question.

        Args:
            answer: True for yes (right), False for no (left)
        """
        if self._current_question >= len(self._questions):
            return

        # Unpack 6-tuple format: (question, trait_key, left_label, right_label, left_meaning, right_meaning)
        question_text, trait_key, left_label, right_label, left_meaning, right_meaning = self._questions[self._current_question]

        # Record answer and its meaning
        self._answers.append(answer)
        meaning = right_meaning if answer else left_meaning
        self._answer_meanings.append(meaning)
        self._prediction_service.record_answer(question_text, answer)

        logger.debug(f"Q: {question_text} -> {answer} ({meaning})")

        # Animation trigger
        self._answer_animation = 1.0

        # Advance or finish
        self._current_question += 1

        if self._current_question >= len(self._questions):
            # All questions answered, start AI processing
            self._start_processing()
        else:
            logger.debug(f"Question {self._current_question}/{len(self._questions)}")

    def _start_processing(self) -> None:
        """Start AI processing (prediction + caricature in parallel)."""
        self._sub_phase = ProphetPhase.PROCESSING
        self.change_phase(ModePhase.PROCESSING)
        self._processing_progress = 0.0

        # Start smart progress tracker
        self._progress_tracker.start()
        self._progress_tracker.advance_to_phase(ProgressPhase.ANALYZING)

        # Initialize Santa runner minigame for the waiting screen
        self._santa_runner = SantaRunner()
        self._santa_runner.reset()

        # Play AI scanning sound
        self._audio.play("prophet_scan", volume=0.5)

        # Start async AI task
        self._ai_task = asyncio.create_task(self._run_ai_generation())

        # Burst particles
        magic = self._particles.get_emitter("magic")
        if magic:
            magic.burst(50)

        logger.info("AI processing started")

    def _build_personality_context(self) -> str:
        """Build a personality context string from questions and answers.

        This provides rich context to AI models about the user's personality
        based on their answers to the fun Gen-Z questions.
        """
        if not self._questions or not self._answer_meanings:
            return ""

        context_parts = ["Профиль личности по ответам:"]
        for i, (q_tuple, meaning) in enumerate(zip(self._questions, self._answer_meanings)):
            question_text = q_tuple[0]
            context_parts.append(f"• {question_text} → {meaning}")

        return "\n".join(context_parts)

    async def _run_ai_generation(self) -> None:
        """Run AI generation tasks in parallel."""
        try:
            # Build personality context from answers
            personality_context = self._build_personality_context()
            logger.info(f"Personality context:\n{personality_context}")

            # Prediction task
            async def generate_prediction():
                if self._photo_data:
                    await self._prediction_service.analyze_photo(self._photo_data)
                return await self._prediction_service.generate_prediction(
                    category=PredictionCategory.MYSTICAL,
                    extra_context=personality_context,
                )

            # Portrait task (NOT caricature - use PROPHET style for natural portrait)
            async def generate_caricature():
                if self._photo_data:
                    return await self._caricature_service.generate_caricature(
                        reference_photo=self._photo_data,
                        style=CaricatureStyle.PROPHET,  # Mystical portrait, NOT exaggerated
                        personality_context=personality_context,
                    )
                else:
                    # No photo, generate simple portrait
                    return await self._caricature_service.generate_simple_caricature(
                        style=CaricatureStyle.PROPHET
                    )

            # Run in parallel
            prediction_task = asyncio.create_task(generate_prediction())
            caricature_task = asyncio.create_task(generate_caricature())

            # Advance to text generation phase
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_TEXT)

            # Wait for both (with timeout)
            try:
                self._prediction = await asyncio.wait_for(prediction_task, timeout=60.0)
                # Prediction done, advance to image generation
                self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)
            except asyncio.TimeoutError:
                logger.warning("Prediction generation timed out")
                self._prediction = self._prediction_service._fallback_prediction()
                self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)

            try:
                self._caricature = await asyncio.wait_for(caricature_task, timeout=120.0)
                # Image done, advance to finalizing
                self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)

                # Upload caricature for QR sharing
                if self._caricature and self._caricature.image_data:
                    logger.info("Starting caricature upload for QR sharing")
                    self._uploader.upload_bytes(
                        self._caricature.image_data,
                        prefix="caricature",
                        extension="png",
                        content_type="image/png",
                        callback=self._on_upload_complete
                    )
            except asyncio.TimeoutError:
                logger.warning("Caricature generation timed out")
                self._caricature = None
                self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)

            logger.info("AI generation complete")

        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            # Use fallback prediction
            self._prediction = self._prediction_service._fallback_prediction()

    def _on_upload_complete(self, result: UploadResult) -> None:
        """Handle completion of S3 upload for QR sharing."""
        if result.success:
            self._qr_url = result.url
            self._qr_image = result.qr_image
            logger.info(f"Caricature uploaded successfully: {self._qr_url}")
        else:
            logger.error(f"Caricature upload failed: {result.error}")

    def _on_ai_complete(self) -> None:
        """Handle completion of AI processing."""
        self._processing_progress = 1.0
        self._progress_tracker.complete()
        self._audio.play_success()
        logger.info("AI complete, finishing mode - manager handles result display")
        # Skip mode's result phase - manager's result view is cleaner
        self._finish()

    def _paginate_prediction(self) -> None:
        """Split prediction text into static pages for display.

        Page structure:
        - Pages 0 to N-1: Text pages
        - Page N: Image (caricature) if available
        - Page N+1: QR code (if available)
        """
        from artifact.graphics.text_utils import smart_wrap_text, MAIN_DISPLAY_WIDTH
        from artifact.graphics.fonts import load_font

        if not self._prediction:
            self._text_pages = []
            self._total_pages = 1  # Just image
            return

        font = load_font("cyrillic")
        margin = 6
        available_width = MAIN_DISPLAY_WIDTH - margin * 2

        # Wrap text at scale 2 (larger, more readable)
        all_lines = smart_wrap_text(self._prediction.text, available_width, font, scale=2)

        # Split into pages of N lines each
        self._text_pages = []
        for i in range(0, len(all_lines), self._lines_per_page):
            page_lines = all_lines[i:i + self._lines_per_page]
            self._text_pages.append(page_lines)

        # Total pages: text pages + image (if available) + QR (if available)
        has_image = self._caricature is not None
        has_qr = self._qr_image is not None or self._uploader.is_uploading
        self._total_pages = len(self._text_pages) + (1 if has_image else 0) + (1 if has_qr else 0)

        # Ensure at least 1 page
        if self._total_pages == 0:
            self._total_pages = 1

        logger.info(f"Paginated prediction: {len(all_lines)} lines -> {len(self._text_pages)} text pages, total {self._total_pages} pages")

    def _get_page_type(self, page_num: int) -> str:
        """Determine what type of content is on a given page number.

        Page structure:
        - Pages 0 to len(text_pages)-1: Text pages
        - Next page: Image (if available)
        - Last page: QR (if available)
        """
        # Text pages first
        if page_num < len(self._text_pages):
            return "text"

        # Then image page
        if self._caricature:
            image_page = len(self._text_pages)
            if page_num == image_page:
                return "image"

            # Then QR page
            if self._qr_image is not None or self._uploader.is_uploading:
                qr_page = image_page + 1
                if page_num == qr_page:
                    return "qr"
        else:
            # No image, check for QR directly after text
            if self._qr_image is not None or self._uploader.is_uploading:
                qr_page = len(self._text_pages)
                if page_num == qr_page:
                    return "qr"

        return "text"  # Fallback

    def _get_nav_hint(self) -> str:
        """Get navigation hint showing current page and arrows."""
        if self._total_pages <= 1:
            return "КНОПКА = ПЕЧАТЬ"

        # Show compact page indicator with arrows
        page_num = self._current_page + 1
        total = self._total_pages

        left_arrow = "◄" if self._current_page > 0 else " "
        right_arrow = "►" if self._current_page < self._total_pages - 1 else " "

        return f"{left_arrow} {page_num}/{total} {right_arrow} ПЕЧАТЬ"

    def on_exit(self) -> None:
        """Cleanup."""
        # Cancel any pending AI task
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()

        # Clear camera reference (shared service, don't close)
        self._camera = None
        self._camera_frame = None

        self._particles.clear_all()
        self.stop_animations()

    def _finish(self) -> None:
        """Complete the mode."""
        prediction_text = ""
        if self._prediction:
            prediction_text = self._prediction.text
            # Note: No lucky number added - each prediction is unique!

        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=prediction_text,
            ticker_text=prediction_text,
            lcd_text="ОРАКУЛ".center(16),
            should_print=True,
            print_data={
                "prediction": prediction_text,
                "caricature": self._caricature.image_data if self._caricature else None,
                "qr_url": self._qr_url,
                "qr_image": self._qr_image,
                "answers": self._answers,
                "timestamp": datetime.now().isoformat(),
                "type": "ai_prophet"
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        """Render main display."""
        from artifact.graphics.primitives import fill, draw_circle, draw_rect, draw_line
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        # Dark tech background
        fill(buffer, (5, 10, 20))

        font = load_font("cyrillic")

        if self._sub_phase == ProphetPhase.INTRO:
            self._render_intro(buffer, font)

        elif self._sub_phase == ProphetPhase.CAMERA_PREP:
            self._render_camera_prep(buffer, font)

        elif self._sub_phase == ProphetPhase.CAMERA_CAPTURE:
            self._render_camera_capture(buffer, font)

        elif self._sub_phase == ProphetPhase.QUESTIONS:
            self._render_questions(buffer, font)

        elif self._sub_phase == ProphetPhase.PROCESSING:
            self._render_processing(buffer, font)

        elif self._sub_phase in (ProphetPhase.REVEAL, ProphetPhase.RESULT):
            self._render_result(buffer, font)

        # Render particles on top
        self._particles.render(buffer)

        # Flash effect
        if self._flash_alpha > 0:
            alpha = int(255 * self._flash_alpha)
            fill(buffer, (alpha, alpha, alpha))

    def _render_intro(self, buffer, font) -> None:
        """Render intro animation."""
        from artifact.graphics.primitives import draw_circle
        from artifact.graphics.text_utils import draw_centered_text

        # Pulsing eye/orb
        pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 300)
        radius = int(30 * pulse)

        # Outer glow
        for r in range(radius + 20, radius, -2):
            alpha = (r - radius) / 20 * 0.5
            color = tuple(int(c * alpha) for c in self._secondary)
            draw_circle(buffer, 64, 45, r, color, filled=False)

        # Core
        draw_circle(buffer, 64, 45, radius, self._primary)
        draw_circle(buffer, 64, 45, radius - 5, (30, 50, 80))

        # Inner highlight
        draw_circle(buffer, 58, 39, 8, (100, 150, 200))

        # Title - centered, positioned within safe zone
        draw_centered_text(buffer, "ОРАКУЛ", 88, self._accent, scale=2)
        draw_centered_text(buffer, "Судьба ждёт", 106, (100, 100, 120), scale=1)

    def _render_camera_prep(self, buffer, font) -> None:
        """Render camera preparation screen with live dithered preview."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text
        import numpy as np

        # Show live camera preview if available
        try:
            if self._camera_frame is not None and isinstance(self._camera_frame, np.ndarray):
                if self._camera_frame.shape == buffer.shape:
                    np.copyto(buffer, self._camera_frame)
        except Exception as e:
            logger.debug(f"Camera frame render error: {e}")

        # Overlay text on top of the preview - within safe zone
        draw_centered_text(buffer, "СМОТРИ В КАМЕРУ", 100, self._accent, scale=1)
        draw_centered_text(buffer, "ПРИГОТОВЬСЯ...", 112, (255, 200, 100), scale=1)

    def _render_camera_capture(self, buffer, font) -> None:
        """Render camera capture with countdown and live preview."""
        from artifact.graphics.primitives import draw_circle, draw_rect, fill
        from artifact.graphics.text_utils import draw_centered_text
        import numpy as np

        # Show live camera preview as background
        try:
            if self._camera_frame is not None and isinstance(self._camera_frame, np.ndarray):
                if self._camera_frame.shape == buffer.shape:
                    np.copyto(buffer, self._camera_frame)
        except Exception as e:
            logger.debug(f"Camera frame render error: {e}")

        # Countdown number - large and centered
        if self._camera_countdown > 0:
            countdown_num = str(int(self._camera_countdown) + 1)
            scale = 4 + int((self._camera_countdown % 1) * 2)
            draw_centered_text(buffer, countdown_num, 45, (255, 255, 255), scale=scale)

            # Progress ring around countdown
            progress = 1.0 - (self._camera_countdown % 1)
            for angle in range(0, int(360 * progress), 10):
                rad = math.radians(angle - 90)
                px = int(64 + 45 * math.cos(rad))
                py = int(64 + 45 * math.sin(rad))
                draw_circle(buffer, px, py, 2, self._secondary)

        # Flash effect when capturing
        if self._flash_alpha > 0:
            # White flash overlay
            flash_color = tuple(int(255 * self._flash_alpha) for _ in range(3))
            # Blend flash into buffer
            buffer[:, :] = np.clip(
                buffer.astype(np.int16) + int(255 * self._flash_alpha),
                0, 255
            ).astype(np.uint8)
            draw_centered_text(buffer, "ФОТО!", 60, (50, 50, 50), scale=2)

    def _render_questions(self, buffer, font) -> None:
        """Render binary question screen with animated effects."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.fonts import draw_text_bitmap
        from artifact.graphics.text_utils import (
            draw_animated_text, draw_centered_text, draw_wrapped_text,
            TextEffect, smart_wrap_text, MAIN_DISPLAY_WIDTH
        )

        if self._current_question >= len(self._questions):
            return

        # Unpack question - now includes button labels!
        # Format: (text, trait_key, left_label, right_label, left_meaning, right_meaning)
        q = self._questions[self._current_question]
        question_text = q[0]
        left_label = q[2]   # e.g., "НЕТ" or "ДЕНЬГИ"
        right_label = q[3]  # e.g., "ДА" or "СЛАВА"

        # Question number with glow - compact at top
        q_num = f"{self._current_question + 1}/{len(self._questions)}"
        draw_animated_text(buffer, q_num, 2, self._secondary, self._time_in_phase, TextEffect.GLOW, scale=1)

        # Question text - try scale=2 first, fallback to scale=1 for long questions
        margin = 4
        available_width = MAIN_DISPLAY_WIDTH - margin * 2
        lines_s2 = smart_wrap_text(question_text, available_width, font, scale=2)

        # Use scale=2 if fits in 4 lines, else scale=1
        if len(lines_s2) <= 4:
            lines = lines_s2
            scale = 2
            line_height = 16
            start_y = 14
        else:
            lines = smart_wrap_text(question_text, available_width, font, scale=1)
            scale = 1
            line_height = 10
            start_y = 14

        # Draw wrapped question text centered
        y = start_y
        max_lines = 4 if scale == 2 else 6
        for i, line in enumerate(lines[:max_lines]):
            # Pulse effect for emphasis
            pulse = 0.85 + 0.15 * math.sin(self._time_in_phase / 300 + i * 0.3)
            color = tuple(int(255 * pulse) for _ in range(3))
            draw_centered_text(buffer, line, y, color, scale=scale)
            y += line_height

        # Answer buttons - positioned below question text
        btn_y = 92
        btn_h = 20

        # Determine button highlight based on answer
        left_active = self._answer_animation > 0 and len(self._answers) > 0 and not self._answers[-1]
        right_active = self._answer_animation > 0 and len(self._answers) > 0 and self._answers[-1]

        # Button backgrounds with pulse effect
        left_pulse = 1.0 + 0.3 * math.sin(self._time_in_phase / 200) if left_active else 1.0
        right_pulse = 1.0 + 0.3 * math.sin(self._time_in_phase / 200) if right_active else 1.0

        def _clamp_color(values, pulse):
            return tuple(min(255, int(c * pulse)) for c in values)

        left_color = _clamp_color((255, 100, 100) if left_active else (100, 50, 50), left_pulse)
        right_color = _clamp_color((100, 255, 100) if right_active else (50, 100, 50), right_pulse)

        # Draw button boxes
        draw_rect(buffer, 4, btn_y, 56, btn_h, left_color)
        draw_rect(buffer, 68, btn_y, 56, btn_h, right_color)

        # Draw DYNAMIC button labels from question data
        # Left button with arrow
        left_text = f"<{left_label}"
        left_w, _ = font.measure_text(left_text)
        left_x = 4 + (56 - left_w) // 2
        left_text_pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 300)
        left_text_color = tuple(int(255 * left_text_pulse) for _ in range(3))
        draw_text_bitmap(buffer, left_text, left_x, btn_y + 5, left_text_color, font, scale=1)

        # Right button with arrow
        right_text = f"{right_label}>"
        right_w, _ = font.measure_text(right_text)
        right_x = 68 + (56 - right_w) // 2
        right_text_pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 300 + math.pi)
        right_text_color = tuple(int(255 * right_text_pulse) for _ in range(3))
        draw_text_bitmap(buffer, right_text, right_x, btn_y + 5, right_text_color, font, scale=1)

        # Hint at bottom - safe Y position
        draw_centered_text(buffer, "< / >", 114, (80, 80, 100), scale=1)

    def _render_processing(self, buffer, font) -> None:
        """Render Santa runner minigame while AI is processing, with camera as background."""
        from artifact.graphics.primitives import draw_rect, fill
        from artifact.graphics.text_utils import draw_centered_text

        # Get live camera frame for background
        camera_bg = camera_service.get_frame(timeout=0)

        # Render the Santa runner game with camera background
        if self._santa_runner:
            self._santa_runner.render(buffer, background=camera_bg)

            # Add compact progress bar at the top
            bar_w, bar_h = 100, 4
            bar_x = (128 - bar_w) // 2
            bar_y = 2

            # Semi-transparent dark background for progress bar
            draw_rect(buffer, bar_x - 2, bar_y - 1, bar_w + 4, bar_h + 2, (20, 20, 40))

            # Use the SmartProgressTracker's render method for the progress bar
            self._progress_tracker.render_progress_bar(
                buffer, bar_x, bar_y, bar_w, bar_h,
                bar_color=self._accent,
                bg_color=(40, 40, 60),
                time_ms=self._time_in_phase
            )

            # Show compact status at bottom
            status_message = self._progress_tracker.get_message()
            # Semi-transparent dark strip for text
            draw_rect(buffer, 0, 118, 128, 10, (20, 20, 40))
            draw_centered_text(buffer, status_message, 119, (150, 150, 170), scale=1)

        else:
            # Fallback to simple processing screen if no game
            fill(buffer, (5, 10, 20))
            draw_centered_text(buffer, "АНАЛИЗ...", 55, self._accent, scale=2)

    def _render_result(self, buffer, font) -> None:
        """Render prediction result with PAGE-BASED navigation.

        Page structure:
        - Pages 0-N: Static text pages (no scrolling!)
        - Next page: Image (caricature) if available
        - Last page: Full-screen QR code if available
        """
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text

        if self._sub_phase == ProphetPhase.REVEAL:
            # During reveal, show first text page with fade-in effect
            self._render_page_text(buffer, font, 0)
            return

        # Determine what to render based on current page
        page_type = self._get_page_type(self._current_page)

        if page_type == "text":
            text_page_idx = self._current_page
            self._render_page_text(buffer, font, text_page_idx)
        elif page_type == "image":
            self._render_page_image(buffer, font)
        elif page_type == "qr":
            self._render_page_qr(buffer, font)

    def _render_page_text(self, buffer, font, text_page_idx: int) -> None:
        """Render a static text page (no scrolling!).

        Displays pre-paginated lines at scale 2, centered on screen.
        """
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text

        # Dark tech background
        fill(buffer, (5, 10, 20))

        if text_page_idx < 0 or text_page_idx >= len(self._text_pages):
            draw_centered_text(buffer, "НЕТ ТЕКСТА", 55, (100, 100, 100), scale=2)
            return

        lines = self._text_pages[text_page_idx]
        scale = 2
        line_height = 20  # Spacing for scale 2

        # Calculate starting Y to vertically center text block
        total_height = len(lines) * line_height
        start_y = max(8, (100 - total_height) // 2)  # Leave room for nav hint

        # Render each line with subtle wave animation
        for i, line in enumerate(lines):
            # Subtle wave effect
            wave_offset = int(1.5 * math.sin(self._time_in_phase / 300 + i * 0.5))
            y = start_y + i * line_height + wave_offset

            # Subtle pulse
            pulse = 0.9 + 0.1 * math.sin(self._time_in_phase / 400 + i * 0.3)
            color = tuple(int(255 * pulse) for _ in range(3))

            draw_centered_text(buffer, line, y, color, scale=scale)

        # Navigation hint at bottom
        hint = self._get_nav_hint()
        draw_centered_text(buffer, hint, 114, (100, 150, 200), scale=1)

    def _render_page_image(self, buffer, font) -> None:
        """Render the caricature/image page."""
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text
        from io import BytesIO
        import numpy as np

        # Dark background
        fill(buffer, (5, 10, 20))

        if not self._caricature:
            # No image - show placeholder
            draw_centered_text(buffer, "НЕТ ФОТО", 55, (100, 100, 100), scale=2)
            hint = self._get_nav_hint()
            draw_centered_text(buffer, hint, 114, (100, 150, 200), scale=1)
            return

        try:
            from PIL import Image

            img = Image.open(BytesIO(self._caricature.image_data))
            img = img.convert("RGB")

            # Fill most of screen (leave room for nav hint)
            display_size = 108
            img = img.resize((display_size, display_size), Image.Resampling.LANCZOS)

            x_offset = (128 - display_size) // 2
            y_offset = 2

            # Copy image to buffer
            img_array = np.array(img, dtype=np.uint8)
            y_end = min(y_offset + display_size, 128)
            x_end = min(x_offset + display_size, 128)
            img_h = y_end - y_offset
            img_w = x_end - x_offset
            buffer[y_offset:y_end, x_offset:x_end] = img_array[:img_h, :img_w]

            # Navigation hint at bottom
            hint = self._get_nav_hint()
            draw_centered_text(buffer, hint, 114, (100, 150, 200), scale=1)

        except Exception as e:
            logger.warning(f"Failed to render caricature: {e}")
            draw_centered_text(buffer, "ОШИБКА", 55, (255, 100, 100), scale=2)

    def _render_page_qr(self, buffer, font) -> None:
        """Render full-screen QR code page (last page)."""
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text
        import numpy as np

        if self._qr_image is not None:
            # White background for QR visibility
            fill(buffer, (255, 255, 255))

            qr_h, qr_w = self._qr_image.shape[:2]

            # Scale QR to fill most of the screen
            target_size = 120
            if qr_h != target_size or qr_w != target_size:
                from PIL import Image
                qr_pil = Image.fromarray(self._qr_image)
                qr_pil = qr_pil.resize((target_size, target_size), Image.Resampling.NEAREST)
                qr_scaled = np.array(qr_pil)
            else:
                qr_scaled = self._qr_image

            qr_h, qr_w = qr_scaled.shape[:2]
            x_offset = (128 - qr_w) // 2
            y_offset = (128 - qr_h) // 2

            buffer[y_offset:y_offset + qr_h, x_offset:x_offset + qr_w] = qr_scaled

        elif self._uploader.is_uploading:
            fill(buffer, (20, 20, 30))
            draw_centered_text(buffer, "ЗАГРУЗКА", 45, (200, 200, 100), scale=2)
            draw_centered_text(buffer, "QR КОДА...", 70, (150, 150, 150), scale=1)
        else:
            fill(buffer, (20, 20, 30))
            draw_centered_text(buffer, "QR", 45, (100, 100, 100), scale=2)
            draw_centered_text(buffer, "НЕ ГОТОВ", 70, (100, 100, 100), scale=1)

        # Hint stays on ticker/LCD for full-screen QR

    def render_ticker(self, buffer) -> None:
        """Render ticker with smooth seamless scrolling."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, render_ticker_static, TickerEffect, TextEffect

        clear(buffer)

        if self._sub_phase == ProphetPhase.INTRO:
            # Intro with sparkle
            render_ticker_animated(
                buffer, "ОРАКУЛ - СУДЬБА ЖДЁТ",
                self._time_in_phase, self._primary,
                TickerEffect.SPARKLE_SCROLL, speed=0.025
            )

        elif self._sub_phase in (ProphetPhase.CAMERA_PREP, ProphetPhase.CAMERA_CAPTURE):
            # Camera phase with pulse
            render_ticker_animated(
                buffer, "СМОТРИ В КАМЕРУ",
                self._time_in_phase, self._accent,
                TickerEffect.PULSE_SCROLL, speed=0.028
            )

        elif self._sub_phase == ProphetPhase.QUESTIONS:
            # Question indicator as static centered text
            text = f"ВОПРОС {self._current_question + 1}/{len(self._questions)}"
            render_ticker_static(
                buffer, text,
                self._time_in_phase, self._accent,
                TextEffect.GLOW
            )

        elif self._sub_phase == ProphetPhase.PROCESSING:
            # Processing with glitch effect
            render_ticker_animated(
                buffer, "ИИ АНАЛИЗИРУЕТ СУДЬБУ",
                self._time_in_phase, self._secondary,
                TickerEffect.GLITCH_SCROLL, speed=0.03
            )

        elif self._sub_phase == ProphetPhase.RESULT and self._prediction:
            # Result prediction with wave
            render_ticker_animated(
                buffer, self._prediction.text,
                self._time_in_phase, self._accent,
                TickerEffect.WAVE_SCROLL, speed=0.022
            )

        else:
            # Default fallback
            render_ticker_animated(
                buffer, "ОРАКУЛ",
                self._time_in_phase, self._primary,
                TickerEffect.SPARKLE_SCROLL, speed=0.025
            )

    def get_lcd_text(self) -> str:
        """Get LCD text with fun symbols."""
        if self._sub_phase == ProphetPhase.CAMERA_PREP:
            # Blinking eye effect
            frame = int(self._time_in_phase / 300) % 2
            eye = "◉" if frame == 0 else "◎"
            return f" {eye} В КАМЕРУ {eye} ".center(16)[:16]
        elif self._sub_phase == ProphetPhase.CAMERA_CAPTURE:
            countdown = int(self._camera_countdown) + 1
            return f" ★ ФОТО: {countdown} ★ ".center(16)[:16]
        elif self._sub_phase == ProphetPhase.QUESTIONS:
            # Use arrows instead of Л/П
            return f"← НЕТ ○ → ДА".center(16)[:16]
        elif self._sub_phase == ProphetPhase.PROCESSING:
            # Animated thinking
            dots = "◐◓◑◒"
            dot = dots[int(self._time_in_phase / 200) % 4]
            return f" {dot} ИИ ДУМАЕТ {dot} ".center(16)[:16]
        elif self._sub_phase == ProphetPhase.RESULT:
            return " ★ ПРОРОЧЕСТВО ★ ".center(16)[:16]
        return " ◆ ОРАКУЛ ◆ ".center(16)
