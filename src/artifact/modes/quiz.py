"""Quiz mode - Who Wants to Be a Millionaire style.

Russian Gen-Z culture trivia with dramatic effects, sounds, and 4 answer options.
Styled after "Кто хочет стать миллионером" with prize ladder and lifelines.
Winners get a personalized victory doodle!
"""

from typing import List, Tuple, Optional, Dict
import random
import math
import os
import asyncio
import logging
from datetime import datetime

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.ai.client import get_gemini_client, GeminiModel
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.utils.camera import floyd_steinberg_dither, create_viewfinder_overlay
from artifact.utils.camera_service import camera_service

logger = logging.getLogger(__name__)


# =============================================================================
# QUESTION DATABASE - Russian Rap & Pop Culture 2020-2025
# Format: (question, [option_A, option_B, option_C, option_D], correct_index 0-3)
# NO GAMING QUESTIONS - Focus on music, memes, social media, TV
# =============================================================================

QUIZ_QUESTIONS: List[Tuple[str, List[str], int]] = [
    # ===========================================================================
    # RUSSIAN RAP 2023-2025 (Modern Era)
    # ===========================================================================
    ("Кто спел 'Я БУДУ ЕБАТЬ' в 2023?", ["ИНСТАСАМКА", "Клава Кока", "Zivert", "ANNA ASTI"], 0),
    ("Трек 'ФОНК' исполняет?", ["ИНСТАСАМКА", "MAYOT", "OG Buda", "Платина"], 0),
    ("Кто такой MAYOT?", ["Рэпер из Казани", "Продюсер", "DJ", "Блогер"], 0),
    ("Альбом 'ГОРЫ' выпустил?", ["MAYOT", "SALUKI", "Aarne", "Lida"], 0),
    ("Трек 'ПЯТНИЦА' чей?", ["INSTASAMKA", "Zivert", "ANNA ASTI", "Мари Краймбрери"], 0),
    ("Кто записал 'DOPAMINE'?", ["INSTASAMKA", "Клава Кока", "Ёлка", "Дора"], 0),
    ("Лейбл INSTASAMKA?", ["Тут свои", "Black Star", "Gazgolder", "Warner"], 0),
    ("Aarne это?", ["Продюсер-рэпер", "Певица", "DJ", "Блогер"], 0),
    ("Трек 'LAMBO URUS' чей?", ["OG Buda и MAYOT", "Big Baby Tape", "SALUKI", "Платина"], 0),
    ("Кто такой SALUKI?", ["Рэпер", "Продюсер", "Стример", "Актёр"], 0),
    ("Young P&H это?", ["Рэп-дуэт", "Лейбл", "Продюсер", "DJ"], 0),
    ("Трек 'TOXIC' от?", ["INSTASAMKA", "Клава Кока", "Zivert", "Мот"], 0),
    ("Альбом 'Красота и уродство' чей?", ["Oxxxymiron", "Скриптонит", "Хаски", "Face"], 0),
    ("Кто такой Lida?", ["Рэпер", "DJ", "Продюсер", "Блогер"], 0),
    ("Трек 'BENZO' исполняет?", ["Lida", "MAYOT", "OG Buda", "Платина"], 0),
    ("Кто записал 'Аллигатор'?", ["Скриптонит", "Oxxxymiron", "Баста", "Хаски"], 0),
    ("Рэпер SEEMEE откуда?", ["Россия", "Казахстан", "Украина", "Беларусь"], 0),
    ("Трек 'MONEY' 2024 чей?", ["INSTASAMKA", "MAYOT", "Aarne", "Lida"], 0),
    ("Кто такой 163ONMYNECK?", ["Рэпер", "Продюсер", "DJ", "Блогер"], 0),
    ("'Дом с Нормальными Явлениями' альбом?", ["Скриптонит", "Oxxxymiron", "ATL", "Хаски"], 0),
    ("Трек 'BARBIE GIRL' ремейк от?", ["INSTASAMKA", "Клава Кока", "Zivert", "ANNA ASTI"], 0),
    ("Рэп-батл площадка 140 BPM это?", ["YouTube шоу", "Клуб", "Лейбл", "Фестиваль"], 0),

    # ===========================================================================
    # RUSSIAN RAP CLASSICS & LEGENDS (2020-2022)
    # ===========================================================================
    ("Кто записал 'CADILLAC'?", ["MORGENSHTERN и Элджей", "Big Baby Tape", "OG Buda", "Face"], 0),
    ("Трек 'Ратататата' с кем записан?", ["MORGENSHTERN и Витя АК", "Элджей", "Face", "Pharaoh"], 0),
    ("Трек 'Дико тусим' от?", ["Big Baby Tape", "OG Buda", "MAYOT", "Платина"], 0),
    ("Кто такой Big Baby Tape?", ["Рэпер из Москвы", "DJ", "Продюсер", "Блогер"], 0),
    ("Трек 'KILLA' исполняет?", ["OG Buda", "Big Baby Tape", "MAYOT", "Платина"], 0),
    ("Альбом 'BENTLEY BENTAYGA' чей?", ["Big Baby Tape", "OG Buda", "MAYOT", "Скриптонит"], 0),
    ("Booking Machine это лейбл?", ["Скриптонита", "Oxxxymiron", "Басты", "Тимати"], 0),
    ("Трек 'Положение' от?", ["Скриптонит", "Oxxxymiron", "ATL", "Хаски"], 0),
    ("Кто записал 'Пламя'?", ["Скриптонит", "Баста", "Noize MC", "Oxxxymiron"], 0),
    ("Альбом 'Уроборос' выпустил?", ["Скриптонит", "Oxxxymiron", "Хаски", "Face"], 0),

    # ===========================================================================
    # RUSSIAN POP & R&B 2023-2025
    # ===========================================================================
    ("Трек 'По барам' от?", ["ANNA ASTI", "Zivert", "INSTASAMKA", "Клава Кока"], 0),
    ("Кто такая ANNA ASTI?", ["Певица", "Рэперша", "DJ", "Блогер"], 0),
    ("Трек 'Царица' от?", ["ANNA ASTI", "Zivert", "Клава Кока", "Ёлка"], 0),
    ("Zivert хит 2020?", ["Beverly Hills", "Life", "Credo", "Все"], 0),
    ("Трек 'Credo' исполняет?", ["Zivert", "ANNA ASTI", "Клава Кока", "Мари Краймбрери"], 0),
    ("Кто такая Клава Кока?", ["Певица", "Рэперша", "DJ", "Актриса"], 0),
    ("Дуэт Клава Кока с Niletto?", ["Краш", "Любовь", "Лето", "Ночь"], 0),
    ("Niletto хит?", ["Любимка", "Краш", "Лето", "Все"], 0),
    ("Хит JONY?", ["Комета", "Звезда", "Луна", "Солнце"], 0),
    ("Rauf & Faik это?", ["Братья", "Друзья", "Одноклассники", "Родственники"], 0),
    ("Трек 'Детство' от?", ["Rauf & Faik", "JONY", "HammAli & Navai", "Mot"], 0),
    ("HammAli & Navai хит?", ["Птичка", "Рыбка", "Кошка", "Собака"], 0),
    ("Мари Краймбрери жанр?", ["Поп", "Рэп", "Рок", "Электроника"], 0),
    ("Хит Мари Краймбрери?", ["Пряталась в ванной", "Танцевала", "Летала", "Бежала"], 0),

    # ===========================================================================
    # MEMES & INTERNET CULTURE 2023-2025
    # ===========================================================================
    ("Что значит 'скибиди'?", ["Мем-танец", "Еда", "Одежда", "Игра"], 0),
    ("Skibidi Toilet откуда?", ["YouTube анимация", "ТикТок", "Инстаграм", "ВК"], 0),
    ("Что такое 'сигма'?", ["Крутой одиночка", "Слабак", "Лидер", "Друг"], 0),
    ("Мем 'Патрик Бэйтмен' из какого фильма?", ["Американский психопат", "Джокер", "Бойцовский клуб", "Матрица"], 0),
    ("'Гигачад' это?", ["Идеальный мужчина мем", "Рэпер", "Блогер", "Актёр"], 0),
    ("Что такое 'NPC'?", ["Скучный человек", "Крутой парень", "Умный", "Спортсмен"], 0),
    ("Мем 'Skibidi' создал?", ["DaFuq!?Boom!", "PewDiePie", "MrBeast", "А4"], 0),
    ("'Бусти' это?", ["Платформа подписок", "Соцсеть", "Игра", "Магазин"], 0),
    ("Что такое 'душнила'?", ["Зануда", "Весельчак", "Спортсмен", "Музыкант"], 0),
    ("Мем 'амогус' откуда?", ["Among Us игра", "Фильм", "Сериал", "Книга"], 0),
    ("'W' в интернете означает?", ["Победа", "Поражение", "Вопрос", "Ответ"], 0),
    ("'L' в интернете означает?", ["Поражение", "Победа", "Вопрос", "Ответ"], 0),
    ("Что такое 'редфлаг'?", ["Плохой знак", "Хороший знак", "Вопрос", "Ответ"], 0),
    ("'Гринфлаг' означает?", ["Хороший знак", "Плохой знак", "Вопрос", "Ответ"], 0),

    # ===========================================================================
    # TIKTOK & SOCIAL MEDIA 2023-2025
    # ===========================================================================
    ("Кто такая Валерия Чекалина?", ["Блогер-миллионер", "Певица", "Актриса", "DJ"], 0),
    ("Lerchek это?", ["Валерия Чекалина", "Дина Саева", "Милохин", "Покров"], 0),
    ("Кто такой Артемий Лебедев?", ["Дизайнер-блогер", "Рэпер", "DJ", "Актёр"], 0),
    ("Канал 'Редакция' ведёт?", ["Пивоваров", "Дудь", "Собчак", "Парфёнов"], 0),
    ("Кто такой Данила Поперечный?", ["Stand-up комик", "Рэпер", "DJ", "Актёр"], 0),
    ("Stand-Up Club 1 это?", ["YouTube канал", "Клуб", "Лейбл", "Фестиваль"], 0),
    ("Кто такой Руслан Усачёв?", ["Блогер", "Рэпер", "DJ", "Актёр"], 0),
    ("Шоу 'Что было дальше' на канале?", ["LABELCOM", "ТНТ", "СТС", "Первый"], 0),
    ("Ведущие 'Что было дальше'?", ["Щербаков и команда", "Дудь", "Собчак", "Парфёнов"], 0),
    ("Кто такой Алексей Щербаков?", ["Stand-up комик", "Рэпер", "DJ", "Актёр"], 0),
    ("Шоу Щербакова?", ["Стендап", "Подкаст", "Влог", "Обзоры"], 0),
    ("Кто такой Нурлан Сабуров?", ["Stand-up комик", "Рэпер", "DJ", "Актёр"], 0),
    ("Сабуров откуда?", ["Казахстан", "Россия", "Узбекистан", "Кыргызстан"], 0),
    ("Кто такой Азамат Мусагалиев?", ["Комик и актёр", "Рэпер", "DJ", "Блогер"], 0),

    # ===========================================================================
    # TV SHOWS & SERIES 2023-2025
    # ===========================================================================
    ("Сериал 'Слово пацана' год?", ["2023", "2022", "2024", "2021"], 0),
    ("Кто играет Марата в 'Слово пацана'?", ["Иван Янковский", "Леон Кемстач", "Данила Козловский", "Другой"], 0),
    ("Режиссёр 'Слово пацана'?", ["Жора Крыжовников", "Клим Шипенко", "Бондарчук", "Звягинцев"], 0),
    ("'Слово пацана' про какие годы?", ["80-90е", "2000е", "70е", "60е"], 0),
    ("'Слово пацана' снят в каком городе?", ["Казань", "Москва", "Питер", "Екатеринбург"], 0),
    ("Сериал 'Фишер' про кого?", ["Маньяка", "Полицию", "Врачей", "Учителей"], 0),
    ("Сериал 'Комбинация' про что?", ["Группу 90х", "Бизнес", "Спорт", "Медицину"], 0),
    ("Шоу 'Маска' ведёт?", ["Вячеслав Макаров", "Нагиев", "Галустян", "Харламов"], 0),
    ("'Вызов' фильм про?", ["Космос", "Войну", "Спорт", "Бизнес"], 0),
    ("Кто снял 'Вызов'?", ["Клим Шипенко", "Бондарчук", "Звягинцев", "Михалков"], 0),
    ("Актриса 'Вызов'?", ["Юлия Пересильд", "Равшана Куркова", "Ходченкова", "Акиньшина"], 0),
    ("'Чебурашка' фильм год?", ["2023", "2022", "2024", "2021"], 0),
    ("Сборы 'Чебурашка' в России?", ["Рекордные", "Средние", "Низкие", "Провал"], 0),
    ("Шоу 'Comment Out' ведут?", ["Гудков и Харламов", "Дудь", "Собчак", "Нагиев"], 0),
    ("'Лёд 3' фильм про?", ["Фигурное катание", "Хоккей", "Плавание", "Бег"], 0),

    # ===========================================================================
    # RUSSIAN RAP BATTLES & CULTURE
    # ===========================================================================
    ("Кто выиграл Oxxxymiron vs Гнойный?", ["Гнойный", "Oxxxymiron", "Ничья", "Отменили"], 0),
    ("Слава КПСС это?", ["Гнойный", "Рэпер", "Блогер", "Всё верно"], 3),
    ("Versus Battle это?", ["Рэп-баттлы", "Игра", "Лейбл", "Фестиваль"], 0),
    ("Pharaoh сейчас?", ["Активен", "Не активен", "Ушёл", "Неизвестно"], 0),
    ("Лейбл Dead Dynasty существует?", ["Нет уже", "Да", "Переименован", "Неизвестно"], 0),
    ("Boulevard Depo это?", ["Рэпер", "Лейбл", "DJ", "Продюсер"], 0),

    # ===========================================================================
    # TRENDING MUSIC 2024-2025
    # ===========================================================================
    ("Хит 2024 'Страна чудес' от?", ["Wildways", "Три дня дождя", "Нервы", "Бумбокс"], 1),
    ("Группа 'Три дня дождя' жанр?", ["Рок", "Рэп", "Поп", "Электроника"], 0),
    ("Трек 'Звезда' 2024 от?", ["ANNA ASTI", "Zivert", "JONY", "Клава Кока"], 0),
    ("Кто такие 'Нервы'?", ["Рок группа", "Рэперы", "DJ", "Блогеры"], 0),
    ("Хит группы 'Нервы'?", ["Батареи", "Лампочки", "Провода", "Розетки"], 0),
    ("Кто такой XCHO?", ["Певец", "Рэпер", "DJ", "Блогер"], 0),
    ("XCHO хит?", ["Ты и я", "Мы", "Они", "Вы"], 0),
    ("Дуэт GAYAZOV BROTHERS хит?", ["Увезите меня на Дип-хаус", "До встречи", "Пока", "Привет"], 0),
    ("Hammali навсегда с Navai?", ["Распались", "Вместе", "Неизвестно", "Сольно оба"], 0),
    ("Кто такой Ramil?", ["Певец", "Рэпер", "DJ", "Блогер"], 0),

    # ===========================================================================
    # YOUTUBE & CONTENT CREATORS 2023-2025
    # ===========================================================================
    ("Кто такой А4?", ["Ютубер", "Рэпер", "DJ", "Актёр"], 0),
    ("Кто такой Литвин?", ["Блогер", "Рэпер", "DJ", "Актёр"], 0),
    ("Канал Литвина про что?", ["Розыгрыши", "Музыку", "Спорт", "Еду"], 0),
    ("MrBeast русский аналог?", ["А4", "Дудь", "Хованский", "Ивангай"], 0),
    ("Кто такой Артур Бабич?", ["Тиктокер", "Рэпер", "DJ", "Актёр"], 0),
    ("Аня Покров это?", ["Тиктокерша", "Рэперша", "DJ", "Актриса"], 0),

    # ===========================================================================
    # GAMING CULTURE 2023-2025
    # ===========================================================================
    ("В какой игре персонаж Джетт?", ["Valorant", "CS2", "Fortnite", "Overwatch"], 0),
    ("CSGO переименовали в?", ["CS2", "CSGO 2", "Counter-Strike 3", "CS Reborn"], 0),
    ("Baldur's Gate 3 жанр?", ["RPG", "Шутер", "Гонки", "Спорт"], 0),
    ("Hogwarts Legacy про что?", ["Гарри Поттера", "Властелина колец", "Нарнию", "Звёздные войны"], 0),
    ("Alan Wake 2 это?", ["Хоррор", "Шутер", "RPG", "Гонки"], 0),
    ("Starfield создала?", ["Bethesda", "Rockstar", "EA", "Ubisoft"], 0),
    ("Minecraft создал?", ["Notch", "Gabe", "Phil Spencer", "Todd Howard"], 0),
    ("Roblox это?", ["Платформа игр", "Одна игра", "Консоль", "Стрим"], 0),
    ("GTA 6 выйдет когда?", ["2025", "2024", "2026", "2027"], 0),
    ("Elden Ring от?", ["FromSoftware", "Bethesda", "CD Projekt", "Rockstar"], 0),
    ("Fortnite жанр?", ["Battle Royale", "MMORPG", "Симулятор", "Гонки"], 0),
    ("League of Legends жанр?", ["MOBA", "Шутер", "RPG", "Симулятор"], 0),
    ("Геншин Импакт от?", ["miHoYo", "Nintendo", "Sony", "Microsoft"], 0),
    ("Honkai: Star Rail похожа на?", ["Геншин", "Valorant", "CS2", "Fortnite"], 0),
    ("Lethal Company жанр?", ["Хоррор-кооп", "Шутер", "RPG", "Гонки"], 0),

    # ===========================================================================
    # ANIME & MANGA 2023-2025
    # ===========================================================================
    ("Attack on Titan закончился в?", ["2023", "2022", "2024", "2021"], 0),
    ("Demon Slayer про?", ["Охотников на демонов", "Пиратов", "Ниндзя", "Магов"], 0),
    ("One Piece про?", ["Пиратов", "Ниндзя", "Самураев", "Магов"], 0),
    ("Jujutsu Kaisen переводится как?", ["Магическая битва", "Демон убийца", "Наруто", "Блич"], 0),
    ("Chainsaw Man главный герой?", ["Денджи", "Наруто", "Гон", "Танджиро"], 0),
    ("Spy x Family про?", ["Семью шпионов", "Пиратов", "Ниндзя", "Магов"], 0),
    ("My Hero Academia жанр?", ["Супергерои", "Хоррор", "Романтика", "Спорт"], 0),
    ("Solo Leveling анимация от?", ["A-1 Pictures", "MAPPA", "Ufotable", "Wit Studio"], 0),
    ("Blue Lock про?", ["Футбол", "Баскетбол", "Волейбол", "Теннис"], 0),
    ("Haikyuu про?", ["Волейбол", "Футбол", "Баскетбол", "Теннис"], 0),
    ("Frieren жанр?", ["Фэнтези", "Хоррор", "Спорт", "Романтика"], 0),
    ("Oshi no Ko про?", ["Айдолов", "Спорт", "Роботов", "Пиратов"], 0),

    # ===========================================================================
    # TECH & INTERNET 2023-2025
    # ===========================================================================
    ("ChatGPT создала?", ["OpenAI", "Google", "Meta", "Microsoft"], 0),
    ("Нейросеть для картинок?", ["Midjourney", "ChatGPT", "Siri", "Alexa"], 0),
    ("Discord это?", ["Мессенджер", "Игра", "Соцсеть", "Браузер"], 0),
    ("Twitch принадлежит?", ["Amazon", "Google", "Meta", "Microsoft"], 0),
    ("TikTok создала компания?", ["ByteDance", "Meta", "Google", "Tencent"], 0),
    ("VPN используют для?", ["Обхода блокировок", "Игр", "Звонков", "Фото"], 0),
    ("Notion это?", ["Заметки", "Игра", "Соцсеть", "Мессенджер"], 0),
    ("Telegram создал?", ["Дуров", "Цукерберг", "Маск", "Безос"], 0),
    ("iPhone 15 разъём?", ["USB-C", "Lightning", "MicroUSB", "Без разъёма"], 0),
    ("Vision Pro от?", ["Apple", "Meta", "Google", "Samsung"], 0),
    ("Threads от?", ["Meta", "Twitter", "Google", "TikTok"], 0),
    ("BeReal фишка?", ["Случайное время", "Фильтры", "Сторис", "Рилс"], 0),

    # ===========================================================================
    # K-POP & GLOBAL MUSIC 2023-2025
    # ===========================================================================
    ("BTS расшифровывается как?", ["Bangtan Sonyeondan", "Big Top Stars", "Best Teen Sound", "Beat The Stage"], 0),
    ("BLACKPINK участниц?", ["4", "5", "6", "3"], 0),
    ("Stray Kids лейбл?", ["JYP", "SM", "YG", "HYBE"], 0),
    ("NewJeans дебют?", ["2022", "2021", "2023", "2020"], 0),
    ("Песня 'Dynamite' от?", ["BTS", "BLACKPINK", "EXO", "NCT"], 0),
    ("TWICE участниц?", ["9", "7", "8", "6"], 0),
    ("Дуа Липа хит?", ["Levitating", "Flowers", "Anti-Hero", "Unholy"], 0),
    ("The Weeknd хит 2020?", ["Blinding Lights", "Starboy", "Save Your Tears", "Die For You"], 0),
    ("Taylor Swift альбом 2023?", ["1989 TV", "Midnights", "Folklore", "Evermore"], 0),
    ("Harry Styles хит?", ["As It Was", "Watermelon Sugar", "Adore You", "Sign of the Times"], 0),

    # ===========================================================================
    # STREAMING & CONTENT 2023-2025
    # ===========================================================================
    ("'Слово пацана' платформа?", ["Wink", "Netflix", "Кинопоиск", "Okko"], 0),
    ("Netflix российский аналог?", ["Кинопоиск", "Okko", "Wink", "ivi"], 0),
    ("YouTube Shorts максимум?", ["60 секунд", "90 секунд", "30 секунд", "120 секунд"], 0),
    ("Подкаст Дудя?", ["вДудь", "Куда", "Подкаст", "Интервью"], 0),
    ("Squid Game откуда?", ["Корея", "Япония", "Китай", "США"], 0),
    ("Wednesday танец откуда?", ["Netflix", "Disney+", "HBO Max", "Amazon"], 0),
    ("The Last of Us сериал на?", ["HBO", "Netflix", "Amazon", "Disney+"], 0),
    ("Сериал 'Континенталь' про?", ["Джона Уика", "Джеймса Бонда", "Мстителей", "Звёздные войны"], 0),
    ("One Piece live-action на?", ["Netflix", "HBO", "Disney+", "Amazon"], 0),
    ("'Барби' фильм год?", ["2023", "2022", "2024", "2021"], 0),

    # ===========================================================================
    # FASHION & TRENDS 2023-2025
    # ===========================================================================
    ("Y2K мода это стиль?", ["2000-х", "90-х", "80-х", "70-х"], 0),
    ("Streetwear это?", ["Уличная мода", "Деловой стиль", "Спортивная форма", "Вечерние платья"], 0),
    ("Nike коллаб с Travis Scott?", ["Был", "Не было", "Отменили", "Планируется"], 0),
    ("Crocs в 2023 это?", ["Тренд", "Не модно", "Неизвестно", "Для врачей"], 0),
    ("Stanley Cup это?", ["Термокружка тренд", "Хоккей", "Кофе", "Спорт"], 0),
    ("Baggy jeans это?", ["Широкие джинсы", "Узкие джинсы", "Короткие", "Рваные"], 0),
    ("Clean girl aesthetic это?", ["Минимализм", "Яркий макияж", "Готика", "Панк"], 0),
    ("Quiet luxury это?", ["Неброская роскошь", "Громкие бренды", "Спорт", "Гранж"], 0),

    # ===========================================================================
    # VIRAL MOMENTS 2023-2025
    # ===========================================================================
    ("Skibidi Toilet создал?", ["DaFuq!?Boom!", "MrBeast", "PewDiePie", "А4"], 0),
    ("Мем 'Ohio' про?", ["Странные события", "Еду", "Музыку", "Спорт"], 0),
    ("Grimace Shake мем связан с?", ["McDonald's", "Burger King", "KFC", "Subway"], 0),
    ("'Wednesday' танец под песню?", ["Goo Goo Muck", "Thriller", "Monster", "Ghostbusters"], 0),
    ("Barbenheimer это?", ["Барби + Оппенгеймер", "Игра", "Сериал", "Музыка"], 0),
    ("Ice Spice стала известна в?", ["2022-2023", "2020", "2019", "2021"], 0),
    ("'Roman Empire' тренд про?", ["Мысли парней", "Историю", "Игры", "Еду"], 0),
    ("NPC стриминг это?", ["Реакции на донаты", "Игры", "Музыка", "Подкасты"], 0),
    ("'Girl dinner' тренд про?", ["Еду", "Моду", "Музыку", "Танцы"], 0),
    ("'Очень странные дела' сезон 5 выйдет?", ["2025", "2024", "2026", "Отменили"], 0),

    # ===========================================================================
    # RUSSIAN INTERNET SLANG 2024-2025
    # ===========================================================================
    ("Что значит 'кринж'?", ["Стыдно смотреть", "Круто", "Смешно", "Грустно"], 0),
    ("'Рофл' это?", ["Шутка", "Ошибка", "Победа", "Проблема"], 0),
    ("Что такое 'хейтить'?", ["Ненавидеть", "Любить", "Игнорить", "Поддерживать"], 0),
    ("'Вайб' означает?", ["Атмосфера", "Еда", "Одежда", "Музыка"], 0),
    ("Что значит 'зашквар'?", ["Позор", "Успех", "Веселье", "Секрет"], 0),
    ("'Чилить' это?", ["Отдыхать", "Работать", "Бегать", "Учиться"], 0),
    ("Что такое 'флексить'?", ["Хвастаться", "Грустить", "Спать", "Есть"], 0),
    ("'Краш' в сленге это?", ["Объект влюблённости", "Авария", "Еда", "Игра"], 0),
    ("Что значит 'агриться'?", ["Злиться", "Радоваться", "Спать", "Танцевать"], 0),
    ("'Изи' означает?", ["Легко", "Сложно", "Быстро", "Медленно"], 0),
    ("Что такое 'рандом'?", ["Случайность", "Порядок", "План", "Правило"], 0),
    ("'Токсик' это?", ["Неприятный человек", "Напиток", "Игра", "Еда"], 0),

    # ===========================================================================
    # RUSSIAN RAP NEW WAVE 2024-2025
    # ===========================================================================
    ("Кто такой SODA LUV?", ["Рэпер", "DJ", "Продюсер", "Блогер"], 0),
    ("Трек 'MIAMI' от кого?", ["SODA LUV", "MAYOT", "OG Buda", "Платина"], 0),
    ("Кто записал 'Привет'?", ["Баста", "Oxxxymiron", "Скриптонит", "Хаски"], 0),
    ("Группа Cream Soda поёт?", ["Поп-рок", "Рэп", "Металл", "Джаз"], 0),
    ("Кто такой KOSTROMIN?", ["Певец", "Рэпер", "DJ", "Актёр"], 0),
    ("Хит KOSTROMIN?", ["Моя голова винтом", "Моя рука", "Моя нога", "Моё сердце"], 0),
    ("Кто такие Буерак?", ["Рок группа", "Рэп дуэт", "DJ", "Продюсеры"], 0),
    ("Трек 'Молодым' от?", ["Моргенштерн", "Тимати", "Баста", "Элджей"], 0),
    ("Кто такой Toxi$?", ["Рэпер", "Певец", "DJ", "Блогер"], 0),
    ("Рэпер 163ONMYNECK настоящее имя?", ["Тимофей", "Артём", "Денис", "Никита"], 0),

    # ===========================================================================
    # SOCIAL MEDIA TRENDS 2024-2025
    # ===========================================================================
    ("Что такое 'дуэт' в ТикТоке?", ["Реакция на видео", "Танец", "Песня", "Фильтр"], 0),
    ("'Стич' в ТикТоке это?", ["Нарезка видео", "Музыка", "Эффект", "Текст"], 0),
    ("FYP расшифровывается как?", ["For You Page", "Find Your Page", "Fun Young People", "Free Your Phone"], 0),
    ("Что такое 'сторителлинг'?", ["Рассказывание историй", "Танец", "Песня", "Игра"], 0),
    ("'Тренд' в соцсетях это?", ["Популярная тема", "Реклама", "Магазин", "Игра"], 0),
    ("Что значит 'залететь в рекомендации'?", ["Стать популярным", "Упасть", "Проиграть", "Уйти"], 0),
    ("'Контент' это?", ["Содержание", "Контейнер", "Концерт", "Конкурс"], 0),
    ("Что такое 'инфлюенсер'?", ["Лидер мнений", "Программист", "Врач", "Учитель"], 0),

    # ===========================================================================
    # MOVIES & SERIES 2024-2025
    # ===========================================================================
    ("Фильм 'Дюна 2' режиссёр?", ["Дени Вильнёв", "Нолан", "Спилберг", "Скорсезе"], 0),
    ("'Оппенгеймер' получил Оскар?", ["Да", "Нет", "Номинация", "Не участвовал"], 0),
    ("Сериал 'Fallout' от?", ["Amazon", "Netflix", "HBO", "Disney+"], 0),
    ("'Дэдпул 3' с кем?", ["Росомаха", "Тор", "Халк", "Капитан Америка"], 0),
    ("Фильм 'Бедные-несчастные' про?", ["Женщину-эксперимент", "Бедных", "Животных", "Роботов"], 0),
    ("'Shōgun' сериал про?", ["Японию", "Китай", "Корею", "Тайланд"], 0),
    ("Аниме 'Атака титанов' закончилось в?", ["2023", "2024", "2022", "2021"], 0),
    ("Фильм 'Гладиатор 2' выйдет?", ["2024", "2025", "2026", "Отменили"], 0),

    # ===========================================================================
    # GAMING 2024-2025
    # ===========================================================================
    ("Palworld прозвали?", ["Покемоны с пушками", "Майнкрафт 2", "GTA с покемонами", "Зельда"], 0),
    ("Helldivers 2 жанр?", ["Кооп-шутер", "RPG", "Гонки", "Симулятор"], 0),
    ("Final Fantasy VII Rebirth это?", ["Ремейк", "Оригинал", "DLC", "Мод"], 0),
    ("Tekken 8 это?", ["Файтинг", "Шутер", "RPG", "Гонки"], 0),
    ("Dragon's Dogma 2 создала?", ["Capcom", "FromSoftware", "Bethesda", "Rockstar"], 0),
    ("Skull and Bones про?", ["Пиратов", "Космос", "Средневековье", "Современность"], 0),
    ("Like a Dragon: Infinite Wealth про?", ["Якудза", "Дракона", "Космос", "Войну"], 0),
    ("Balatro это?", ["Покер roguelike", "Шутер", "RPG", "Платформер"], 0),

    # ===========================================================================
    # ESPORTS & STREAMERS 2024-2025
    # ===========================================================================
    ("Кто такой s1mple?", ["CS игрок", "Рэпер", "Блогер", "Актёр"], 0),
    ("Команда NAVI откуда?", ["Украина", "Россия", "США", "Швеция"], 0),
    ("Игра Valorant от?", ["Riot Games", "Valve", "Blizzard", "EA"], 0),
    ("Dota 2 The International это?", ["Турнир", "Патч", "Герой", "Режим"], 0),
    ("Кто такой Faker?", ["LoL игрок", "CS игрок", "Dota игрок", "Valorant игрок"], 0),
    ("Faker из какой страны?", ["Корея", "Китай", "США", "Япония"], 0),

    # ===========================================================================
    # RUSSIAN POP CULTURE 2024-2025
    # ===========================================================================
    ("Шоу 'Голос' на каком канале?", ["Первый", "Россия", "НТВ", "СТС"], 0),
    ("'Танцы' шоу на?", ["ТНТ", "Первый", "СТС", "Пятница"], 0),
    ("Камеди Клаб ведёт?", ["Павел Воля", "Нагиев", "Галустян", "Светлаков"], 0),
    ("'Квартал 95' откуда?", ["Украина", "Россия", "Беларусь", "Казахстан"], 0),
    ("Зеленский был в 'Квартал 95'?", ["Да", "Нет", "Иногда", "Продюсер"], 0),
    ("Кто такая Ольга Бузова?", ["Певица-блогер", "Актриса", "Спортсменка", "Политик"], 0),
    ("'Дом 2' закрылся?", ["Да", "Нет", "Переехал", "Реформат"], 0),

    # ===========================================================================
    # TECH CULTURE 2024-2025
    # ===========================================================================
    ("Sora от OpenAI это?", ["Генератор видео", "Чат-бот", "Поиск", "Игра"], 0),
    ("Claude это?", ["AI от Anthropic", "AI от Google", "AI от Meta", "AI от Apple"], 0),
    ("Gemini это AI от?", ["Google", "OpenAI", "Meta", "Microsoft"], 0),
    ("Llama это AI от?", ["Meta", "Google", "OpenAI", "Amazon"], 0),
    ("Apple Vision Pro это?", ["VR/AR очки", "Телефон", "Часы", "Наушники"], 0),
    ("Rabbit R1 это?", ["AI гаджет", "Телефон", "Наушники", "Часы"], 0),
    ("Humane AI Pin носят на?", ["Одежде", "Руке", "Голове", "Ноге"], 0),

    # ===========================================================================
]


# Prize: Free cocktail for winning!
# No money ladder - just the glory and a drink
FREE_COCKTAIL_THRESHOLD = 7  # Need 7/10 correct to win


class QuizPhase:
    INTRO = "intro"
    CAMERA_PREP = "camera_prep"
    CAMERA_CAPTURE = "capture"
    QUESTION = "question"
    THINKING = "thinking"
    REVEAL = "reveal"
    CORRECT = "correct"
    WRONG = "wrong"
    GENERATING = "generating"  # AI generating victory doodle
    RESULT = "result"


class QuizMode(BaseMode):
    """Quiz mode - Who Wants to Be a Millionaire style.

    Features:
    - 10 questions with random selection
    - Win 7+ to get a free cocktail
    - 4 answer options (A, B, C, D)
    - Dramatic reveals and sound effects
    - Photo capture for personalized victory doodle
    - Winners get AI-generated celebration doodle printed!
    """

    name = "quiz"
    display_name = "ВИКТОРИНА"
    description = "Проверь свои знания!"
    icon = "?"
    style = "quiz"
    requires_camera = True
    requires_ai = True
    estimated_duration = 180

    # Game settings
    QUESTIONS_PER_GAME = 10
    THINKING_TIME = 15.0  # seconds per question

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # AI services
        self._gemini_client = get_gemini_client()
        self._caricature_service = CaricatureService()

        # Camera state
        self._camera: Optional[SimulatorCamera] = None
        self._camera_frame: Optional[bytes] = None
        self._photo_data: Optional[bytes] = None
        self._camera_countdown: float = 0.0
        self._flash_alpha: float = 0.0

        # AI results
        self._victory_doodle: Optional[Caricature] = None
        self._ai_task: Optional[asyncio.Task] = None
        self._progress_tracker = SmartProgressTracker(mode_theme="quiz")

        # Game state
        self._questions: List[Tuple[str, List[str], int]] = []
        self._current_question: int = 0
        self._selected_answer: Optional[int] = None  # 0-3
        self._time_remaining: float = 0.0
        self._score: int = 0  # Correct answers
        self._lives: int = 3  # Allow 2 mistakes (3 lives total)
        self._sub_phase = QuizPhase.INTRO
        self._won_cocktail: bool = False

        # Animation state
        self._reveal_progress: float = 0.0
        self._suspense_time: float = 0.0
        self._answer_locked: bool = False
        self._pulse_time: float = 0.0
        self._wrong_display_timer: float = 0.0  # Timer for showing correct/wrong feedback

        # Particles
        self._particles = ParticleSystem()

        # Colors (Millionaire style - dark blue theme)
        self._bg_dark = (5, 15, 40)
        self._bg_light = (20, 40, 80)
        self._gold = (255, 215, 0)
        self._silver = (192, 192, 192)
        self._correct_green = (0, 200, 80)
        self._wrong_red = (220, 50, 50)
        self._option_blue = (30, 80, 160)
        self._option_highlight = (60, 120, 200)
        self._option_selected = (200, 150, 50)

    def on_enter(self) -> None:
        """Initialize millionaire quiz."""
        # Use isolated RNG for true randomness
        import time
        rng = random.Random()
        seed = int(time.time() * 1_000_000) ^ int.from_bytes(os.urandom(4), 'big')
        rng.seed(seed)

        # Select random questions
        self._questions = rng.sample(QUIZ_QUESTIONS, min(self.QUESTIONS_PER_GAME, len(QUIZ_QUESTIONS)))

        # Reset game state
        self._current_question = 0
        self._selected_answer = None
        self._time_remaining = self.THINKING_TIME
        self._score = 0
        self._lives = 3  # 3 lives = 2 allowed mistakes
        self._won_cocktail = False
        self._sub_phase = QuizPhase.INTRO
        self._answer_locked = False
        self._reveal_progress = 0.0
        self._flash_alpha = 0.0
        self._suspense_time = 0.0
        self._pulse_time = 0.0
        self._wrong_display_timer = 0.0

        # Reset camera/AI state
        self._photo_data = None
        self._camera_frame = None
        self._victory_doodle = None
        self._ai_task = None
        self._camera_countdown = 0.0
        self._progress_tracker.reset()

        # Use shared camera service (always running)
        self._camera = camera_service.is_running
        if self._camera:
            logger.info("Camera service ready for Quiz mode")

        # Gold sparkle particles
        gold_sparkle = ParticlePresets.sparkle(x=64, y=64)
        gold_sparkle.color = self._gold
        self._particles.add_emitter("gold", gold_sparkle)

        self.change_phase(ModePhase.INTRO)

    def on_update(self, delta_ms: float) -> None:
        """Update quiz state."""
        self._particles.update(delta_ms)
        self._pulse_time += delta_ms
        self._flash_alpha = max(0, self._flash_alpha - delta_ms / 200)

        # Update camera preview during camera phases
        if self._sub_phase in (QuizPhase.CAMERA_PREP, QuizPhase.CAMERA_CAPTURE):
            self._update_camera_preview()

        if self.phase == ModePhase.INTRO:
            if self._sub_phase == QuizPhase.INTRO:
                # Show intro briefly, then move to camera
                if self._time_in_phase > 2000:
                    self._sub_phase = QuizPhase.CAMERA_PREP
                    self._time_in_phase = 0

            elif self._sub_phase == QuizPhase.CAMERA_PREP:
                # Camera prep for 2 seconds
                if self._time_in_phase > 2000:
                    self._start_camera_capture()

            elif self._sub_phase == QuizPhase.CAMERA_CAPTURE:
                # Countdown
                self._camera_countdown = max(0, 3.0 - self._time_in_phase / 1000)
                if self._camera_countdown <= 0 and self._photo_data is None:
                    self._do_camera_capture()
                    self._flash_alpha = 1.0

                # Move to game after flash
                if self._time_in_phase > 3500:
                    self._sub_phase = QuizPhase.QUESTION
                    self.change_phase(ModePhase.ACTIVE)

        elif self.phase == ModePhase.ACTIVE:
            if self._sub_phase == QuizPhase.QUESTION:
                # Countdown
                if not self._answer_locked:
                    self._time_remaining -= delta_ms / 1000
                    if self._time_remaining <= 0:
                        # Time's up - wrong! Decrement lives!
                        self._lives -= 1
                        logger.info(f"Time's up! Lives remaining: {self._lives}")
                        self._sub_phase = QuizPhase.WRONG
                        self._time_in_phase = 0
                        self._wrong_display_timer = 0

            elif self._sub_phase == QuizPhase.THINKING:
                # Build suspense before reveal
                self._suspense_time += delta_ms
                if self._suspense_time > 2500:
                    self._reveal_answer()

            elif self._sub_phase == QuizPhase.REVEAL:
                self._reveal_progress = min(1.0, self._reveal_progress + delta_ms / 500)
                if self._reveal_progress >= 1.0:
                    question = self._questions[self._current_question]
                    if self._selected_answer == question[2]:
                        self._sub_phase = QuizPhase.CORRECT
                        self._score += 1
                        self._flash_alpha = 1.0
                        gold = self._particles.get_emitter("gold")
                        if gold:
                            gold.burst(50)
                    else:
                        # IMMEDIATELY decrement lives when wrong
                        self._lives -= 1
                        self._sub_phase = QuizPhase.WRONG
                        logger.info(f"Wrong answer! Lives remaining: {self._lives}")
                    self._wrong_display_timer = 0.0  # Reset wrong display timer

            elif self._sub_phase == QuizPhase.CORRECT:
                self._wrong_display_timer += delta_ms
                if self._wrong_display_timer > 2000:
                    self._next_question()

            elif self._sub_phase == QuizPhase.WRONG:
                self._wrong_display_timer += delta_ms
                if self._wrong_display_timer > 2500:
                    if self._lives <= 0:
                        self._finish_game()
                    else:
                        # Continue to next question after wrong answer
                        self._next_question()

        elif self.phase == ModePhase.PROCESSING:
            # Generating victory doodle
            if self._ai_task and self._ai_task.done():
                self._on_ai_complete()

        elif self.phase == ModePhase.RESULT:
            if self._time_in_phase > 15000:
                self._finish()

    def on_input(self, event: Event) -> bool:
        """Handle input - keypad 1-4 for answers, arrows for navigation."""
        if self.phase == ModePhase.ACTIVE and self._sub_phase == QuizPhase.QUESTION:
            if not self._answer_locked:
                # Direct answer selection via keypad 1-4
                if event.type == EventType.KEYPAD_INPUT:
                    key = event.data.get("key", "")
                    if key == "1":
                        self._selected_answer = 0  # A
                        self._lock_answer()
                        return True
                    elif key == "2":
                        self._selected_answer = 1  # B
                        self._lock_answer()
                        return True
                    elif key == "3":
                        self._selected_answer = 2  # C
                        self._lock_answer()
                        return True
                    elif key == "4":
                        self._selected_answer = 3  # D
                        self._lock_answer()
                        return True
                # Navigation via arrows (backup method)
                elif event.type == EventType.ARCADE_LEFT:
                    if self._selected_answer is None or self._selected_answer >= 2:
                        self._selected_answer = 0  # A
                    else:
                        self._selected_answer = (self._selected_answer + 1) % 2  # Toggle A/B
                    return True
                elif event.type == EventType.ARCADE_RIGHT:
                    if self._selected_answer is None or self._selected_answer < 2:
                        self._selected_answer = 2  # C
                    else:
                        self._selected_answer = 2 + (self._selected_answer - 1) % 2  # Toggle C/D
                    return True
                elif event.type == EventType.BUTTON_PRESS:
                    if self._selected_answer is not None:
                        self._lock_answer()
                        return True

        elif self.phase == ModePhase.RESULT:
            if event.type == EventType.BUTTON_PRESS:
                self._finish()
                return True

        return False

    def _lock_answer(self) -> None:
        """Lock in the selected answer."""
        self._answer_locked = True
        self._sub_phase = QuizPhase.THINKING
        self._suspense_time = 0
        self._time_in_phase = 0

    def _reveal_answer(self) -> None:
        """Reveal if answer is correct."""
        self._sub_phase = QuizPhase.REVEAL
        self._reveal_progress = 0.0
        self._time_in_phase = 0

    def _next_question(self) -> None:
        """Move to next question."""
        self._current_question += 1
        if self._current_question >= len(self._questions):
            self._finish_game()
        else:
            self._selected_answer = None
            self._time_remaining = self.THINKING_TIME
            self._answer_locked = False
            self._sub_phase = QuizPhase.QUESTION
            self._suspense_time = 0
            self._reveal_progress = 0
            self._wrong_display_timer = 0

    def _finish_game(self) -> None:
        """End the game and show results."""
        self._won_cocktail = self._score >= FREE_COCKTAIL_THRESHOLD

        # If won and have photo, generate victory doodle!
        if self._won_cocktail and self._photo_data:
            self._sub_phase = QuizPhase.GENERATING
            self.change_phase(ModePhase.PROCESSING)
            # Start progress tracker for victory doodle generation
            self._progress_tracker.start()
            self._progress_tracker.advance_to_phase(ProgressPhase.ANALYZING)
            self._ai_task = asyncio.create_task(self._generate_victory_doodle())
            logger.info("Starting victory doodle generation")
        else:
            self._sub_phase = QuizPhase.RESULT
            self.change_phase(ModePhase.RESULT)

        # Big celebration if won!
        if self._won_cocktail:
            gold = self._particles.get_emitter("gold")
            if gold:
                gold.burst(100)

    def _start_camera_capture(self) -> None:
        """Start the camera capture sequence."""
        self._sub_phase = QuizPhase.CAMERA_CAPTURE
        self._time_in_phase = 0
        self._camera_countdown = 3.0
        logger.info("Quiz camera capture started")

    def _do_camera_capture(self) -> None:
        """Capture the photo."""
        self._photo_data = camera_service.capture_jpeg(quality=90)
        if self._photo_data:
            logger.info(f"Quiz photo captured: {len(self._photo_data)} bytes")
        else:
            logger.warning("Quiz photo capture failed")

    def _update_camera_preview(self) -> None:
        """Update live camera preview."""
        try:
            frame = camera_service.get_frame(timeout=0)
            if frame is not None and frame.size > 0:
                dithered = floyd_steinberg_dither(frame, target_size=(128, 128))
                self._camera_frame = create_viewfinder_overlay(dithered, self._time_in_phase).copy()
                self._camera = True
        except Exception as e:
            logger.warning(f"Quiz camera preview error: {e}")

    async def _generate_victory_doodle(self) -> None:
        """Generate a celebratory doodle for the winner."""
        try:
            if not self._photo_data:
                return

            # Advance to image generation phase
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)

            # Generate victory-themed caricature with QUIZ_WINNER style
            # Designed for 128x128 pixel display with Russian labels
            self._victory_doodle = await self._caricature_service.generate_caricature(
                reference_photo=self._photo_data,
                style=CaricatureStyle.QUIZ_WINNER,
                personality_context=f"ПОБЕДИТЕЛЬ! Набрал {self._score} из {len(self._questions)}! Триумф, праздник, чемпион!"
            )
            if self._victory_doodle:
                logger.info(f"Victory doodle generated: {len(self._victory_doodle.image_data)} bytes")
            else:
                logger.warning("Victory doodle generation returned None")

            # Advance to finalizing
            self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)

        except Exception as e:
            logger.error(f"Victory doodle generation failed: {e}")
            self._victory_doodle = None

    def _on_ai_complete(self) -> None:
        """Handle AI generation completion."""
        self._progress_tracker.complete()
        self._sub_phase = QuizPhase.RESULT
        self.change_phase(ModePhase.RESULT)
        logger.info("Victory doodle ready, showing result")

    def on_exit(self) -> None:
        """Cleanup."""
        # Cancel AI task
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()

        # Clear camera reference (shared service, don't close)
        self._camera = None
        self._camera_frame = None

        self._particles.clear_all()
        self.stop_animations()

    def _finish(self) -> None:
        """Complete the mode."""
        total = len(self._questions)
        pct = int(self._score / total * 100) if total > 0 else 0

        if self._won_cocktail:
            display = "КОКТЕЙЛЬ ТВОЙ!"
            ticker = f"ПОБЕДА! {self._score}/{total} - БЕСПЛАТНЫЙ КОКТЕЙЛЬ!"
            lcd = "КОКТЕЙЛЬ ТВОЙ!"
        else:
            display = f"Счёт: {self._score}/{total}"
            ticker = f"ВИКТОРИНА: {self._score}/{total} ({pct}%)"
            lcd = f"{self._score}/{total} {pct}%"

        result = ModeResult(
            mode_name=self.name,
            success=self._won_cocktail,
            display_text=display,
            ticker_text=ticker,
            lcd_text=lcd[:16].center(16),
            should_print=self._won_cocktail,  # Only print if won
            print_data={
                "score": self._score,
                "total": total,
                "percentage": pct,
                "won_cocktail": self._won_cocktail,
                "type": "quiz",
                "caricature": self._victory_doodle.image_data if self._victory_doodle else None,
                "timestamp": datetime.now().isoformat()
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        """Render main display."""
        from artifact.graphics.primitives import fill, draw_rect, draw_line
        from artifact.graphics.text_utils import draw_centered_text, wrap_text

        # Dark blue gradient background
        fill(buffer, self._bg_dark)

        # Add subtle grid lines for Millionaire feel
        for i in range(0, 128, 16):
            draw_line(buffer, 0, i, 128, i, (15, 30, 60))

        if self.phase == ModePhase.INTRO:
            self._render_intro(buffer)
        elif self.phase == ModePhase.ACTIVE:
            self._render_game(buffer)
        elif self.phase == ModePhase.PROCESSING:
            self._render_generating(buffer)
        elif self.phase == ModePhase.RESULT:
            self._render_result(buffer)

        # Render particles
        self._particles.render(buffer)

        # Flash overlay
        if self._flash_alpha > 0:
            flash_color = tuple(int(255 * self._flash_alpha * 0.3) for _ in range(3))
            fill(buffer, flash_color)

    def _render_intro(self, buffer) -> None:
        """Render intro screen with camera phases."""
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.primitives import draw_circle
        import numpy as np

        if self._sub_phase == QuizPhase.INTRO:
            # Title intro
            pulse = 0.8 + 0.2 * math.sin(self._time_in_phase / 200)
            title_color = tuple(int(c * pulse) for c in self._gold)

            draw_centered_text(buffer, "ВИКТОРИНА", 20, title_color, scale=2)
            draw_centered_text(buffer, f"{self.QUESTIONS_PER_GAME} вопросов", 45, self._silver, scale=1)
            draw_centered_text(buffer, f"{FREE_COCKTAIL_THRESHOLD}+ верно =", 60, (150, 150, 180), scale=1)
            draw_centered_text(buffer, "КОКТЕЙЛЬ!", 75, self._correct_green, scale=2)
            draw_centered_text(buffer, "ГОТОВЬСЯ...", 105, (100, 120, 150), scale=1)

        elif self._sub_phase == QuizPhase.CAMERA_PREP:
            # Camera preview with instructions
            if self._camera_frame is not None and isinstance(self._camera_frame, np.ndarray):
                if self._camera_frame.shape == buffer.shape:
                    np.copyto(buffer, self._camera_frame)

            draw_centered_text(buffer, "СМОТРИ В КАМЕРУ", 95, self._gold, scale=1)
            draw_centered_text(buffer, "СДЕЛАЕМ ФОТО!", 110, (255, 200, 100), scale=1)

        elif self._sub_phase == QuizPhase.CAMERA_CAPTURE:
            # Camera capture with countdown
            if self._camera_frame is not None and isinstance(self._camera_frame, np.ndarray):
                if self._camera_frame.shape == buffer.shape:
                    np.copyto(buffer, self._camera_frame)

            # Big countdown number
            if self._camera_countdown > 0:
                countdown_num = str(int(self._camera_countdown) + 1)
                draw_centered_text(buffer, countdown_num, 50, (255, 255, 255), scale=4)

                # Progress ring
                progress = 1.0 - (self._camera_countdown % 1)
                for angle in range(0, int(360 * progress), 10):
                    rad = math.radians(angle - 90)
                    px = int(64 + 45 * math.cos(rad))
                    py = int(64 + 45 * math.sin(rad))
                    draw_circle(buffer, px, py, 2, self._gold)

    def _render_generating(self, buffer) -> None:
        """Render AI generation screen with progress tracking."""
        from artifact.graphics.text_utils import draw_centered_text

        # Update progress tracker
        self._progress_tracker.update(delta_ms=16)

        pulse = 0.8 + 0.2 * math.sin(self._time_in_phase / 200)
        color = tuple(int(c * pulse) for c in self._gold)

        draw_centered_text(buffer, "ПОБЕДА!", 10, self._correct_green, scale=2)

        # Loading animation in middle area
        self._progress_tracker.render_loading_animation(
            buffer, style="tech", time_ms=self._time_in_phase
        )

        draw_centered_text(buffer, "СОЗДАЁМ ПРИЗ", 55, color, scale=1)

        # Progress bar
        bar_x, bar_y, bar_w, bar_h = 14, 75, 100, 8
        self._progress_tracker.render_progress_bar(
            buffer, bar_x, bar_y, bar_w, bar_h,
            bar_color=self._gold,
            bg_color=(20, 30, 50),
            border_color=(80, 100, 140)
        )

        # Status message
        status_message = self._progress_tracker.get_message()
        draw_centered_text(buffer, status_message, 92, (140, 160, 200), scale=1)

        draw_centered_text(buffer, "Секундочку...", 108, (100, 120, 150), scale=1)

    def _render_game(self, buffer) -> None:
        """Render active game with live camera background."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text, wrap_text, fit_text_in_rect
        import numpy as np

        # LIVE CAMERA BACKGROUND - dimmed and tinted
        frame = camera_service.get_frame(timeout=0)
        if frame is not None and frame.shape[:2] == (128, 128):
            # Dim the camera feed (30% opacity) and add blue tint
            dimmed = (frame.astype(np.float32) * 0.25).astype(np.uint8)
            # Add slight blue tint overlay
            tint = np.array([5, 15, 40], dtype=np.uint8)
            blended = np.clip(dimmed.astype(np.int16) + tint, 0, 255).astype(np.uint8)
            np.copyto(buffer, blended)

        # Add subtle grid lines for Millionaire feel (on top of camera)
        from artifact.graphics.primitives import draw_line
        for i in range(0, 128, 16):
            draw_line(buffer, 0, i, 128, i, (15, 30, 60))

        question = self._questions[self._current_question]
        q_text, options, correct = question

        # Question number, score and lives with semi-transparent background
        header_bg = np.zeros((12, 128, 3), dtype=np.uint8)
        header_bg[:] = (10, 20, 50)
        buffer[:12] = np.clip(buffer[:12].astype(np.int16) * 0.5 + header_bg.astype(np.int16) * 0.7, 0, 255).astype(np.uint8)

        lives_display = "O" * self._lives + "X" * (3 - self._lives)
        draw_centered_text(buffer, f"#{self._current_question + 1}/{self.QUESTIONS_PER_GAME}  {lives_display}  {self._score}", 2, self._gold, scale=1)

        # Timer bar with SMOOTH color transition (green -> yellow -> orange -> red)
        timer_pct = self._time_remaining / self.THINKING_TIME
        timer_w = int(120 * timer_pct)

        # Smooth gradient: green (>60%) -> yellow (30-60%) -> orange (15-30%) -> red (<15%)
        if timer_pct > 0.6:
            timer_color = self._correct_green
        elif timer_pct > 0.3:
            # Blend green to yellow
            t = (timer_pct - 0.3) / 0.3
            timer_color = (
                int(0 + (255 - 0) * (1 - t)),  # R: 0 -> 255
                int(200 + (215 - 200) * (1 - t)),  # G: 200 -> 215
                int(80 * t)  # B: 80 -> 0
            )
        elif timer_pct > 0.15:
            # Blend yellow to orange
            t = (timer_pct - 0.15) / 0.15
            timer_color = (
                255,  # R stays max
                int(150 + (215 - 150) * t),  # G: 150 -> 215
                0
            )
        else:
            # Pulsing red when critical (<15%)
            pulse = 0.7 + 0.3 * math.sin(self._pulse_time / 80)
            timer_color = (int(220 * pulse), int(50 * pulse), int(50 * pulse))

        # Timer background
        draw_rect(buffer, 4, 12, 120, 4, (40, 40, 60))
        if timer_w > 0:
            draw_rect(buffer, 4, 12, timer_w, 4, timer_color)
            # Bright leading edge
            if timer_w > 2:
                draw_rect(buffer, 4 + timer_w - 2, 12, 2, 4, (255, 255, 255))

        # Question text with semi-transparent background panel
        question_panel_y = 18
        question_panel_h = 26
        panel_bg = buffer[question_panel_y:question_panel_y + question_panel_h, 2:126].astype(np.float32)
        panel_overlay = np.full_like(panel_bg, (20, 30, 60), dtype=np.float32)
        buffer[question_panel_y:question_panel_y + question_panel_h, 2:126] = np.clip(
            panel_bg * 0.4 + panel_overlay * 0.6, 0, 255
        ).astype(np.uint8)

        # Question text (wrapped)
        lines = wrap_text(q_text, 20)
        text_y = 22
        for line in lines[:2]:
            draw_centered_text(buffer, line, text_y, (255, 255, 255), scale=1)
            text_y += 11

        # Answer options in 2x2 grid with improved visuals
        option_labels = ["1", "2", "3", "4"]
        positions = [(2, 50), (66, 50), (2, 80), (66, 80)]  # x, y for each option

        for i, (opt, label) in enumerate(zip(options, option_labels)):
            opt_x, opt_y = positions[i]
            w, h = 60, 26

            # Determine color and effects based on state
            glow = False
            shake = 0
            if self._sub_phase == QuizPhase.REVEAL or self._sub_phase in (QuizPhase.CORRECT, QuizPhase.WRONG):
                if i == correct:
                    color = self._correct_green
                    glow = True
                elif i == self._selected_answer and i != correct:
                    color = self._wrong_red
                    # Shake effect for wrong answer
                    shake = int(math.sin(self._wrong_display_timer / 30) * 2)
                else:
                    color = (20, 40, 80)  # Dim non-selected options
            elif i == self._selected_answer:
                # Pulsing selection with glow
                pulse = 0.7 + 0.3 * math.sin(self._pulse_time / 100)
                color = tuple(int(c * pulse) for c in self._option_selected)
                glow = True
            else:
                color = self._option_blue

            # Draw option box with optional glow
            box_x = opt_x + shake
            if glow:
                # Outer glow
                glow_color = tuple(min(255, c + 40) for c in color)
                draw_rect(buffer, box_x - 1, opt_y - 1, w + 2, h + 2, glow_color)

            # Main box with gradient effect (darker at top)
            draw_rect(buffer, box_x, opt_y, w, h, color)
            # Highlight at top
            highlight = tuple(min(255, c + 30) for c in color)
            draw_rect(buffer, box_x, opt_y, w, 2, highlight)
            # Shadow at bottom
            shadow = tuple(max(0, c - 30) for c in color)
            draw_rect(buffer, box_x, opt_y + h - 2, w, 2, shadow)

            # Option text - fit within the option box
            display_text = f"{label}:{opt.upper()}"
            text_color = (255, 255, 255) if color != (20, 40, 80) else (100, 100, 120)
            fit_text_in_rect(buffer, display_text, (box_x, opt_y, w, h), text_color, max_scale=1)

        # Instructions at bottom
        if self._sub_phase == QuizPhase.QUESTION and not self._answer_locked:
            draw_centered_text(buffer, "НАЖМИ 1-4", 118, (100, 120, 150), scale=1)
        elif self._sub_phase == QuizPhase.THINKING:
            dots = "." * (int(self._suspense_time / 300) % 4)
            draw_centered_text(buffer, f"ДУМАЕМ{dots}", 118, self._gold, scale=1)

    def _render_result(self, buffer) -> None:
        """Render final result with victory doodle - POLISHED with celebration effects."""
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.primitives import draw_rect, draw_circle
        import numpy as np

        if self._won_cocktail:
            # Winner! Show doodle or celebration alternating
            show_doodle = self._victory_doodle is not None and (int(self._time_in_phase / 5000) % 2 == 0)

            if show_doodle:
                # Show victory doodle with VECTORIZED rendering
                try:
                    from PIL import Image
                    from io import BytesIO

                    img = Image.open(BytesIO(self._victory_doodle.image_data))
                    img = img.convert("RGB")
                    display_size = 100
                    img = img.resize((display_size, display_size), Image.Resampling.NEAREST)

                    x_offset = (128 - display_size) // 2
                    y_offset = 5

                    # VECTORIZED: Copy entire image array at once
                    img_array = np.array(img, dtype=np.uint8)
                    y_end = min(y_offset + display_size, 128)
                    x_end = min(x_offset + display_size, 128)
                    img_h = y_end - y_offset
                    img_w = x_end - x_offset
                    buffer[y_offset:y_end, x_offset:x_end] = img_array[:img_h, :img_w]

                    # Animated pulsing gold border for extra celebration
                    pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 150)
                    border_color = tuple(int(c * pulse) for c in self._gold)
                    draw_rect(buffer, x_offset - 2, y_offset - 2, display_size + 4, display_size + 4, border_color, filled=False)
                    draw_rect(buffer, x_offset - 3, y_offset - 3, display_size + 6, display_size + 6, border_color, filled=False)

                    # Pulsing victory text
                    draw_centered_text(buffer, "ТВОЙ ПРИЗ!", 112, border_color, scale=1)

                except Exception as e:
                    logger.warning(f"Failed to render victory doodle: {e}")
                    # Fallback to text
                    self._render_winner_text(buffer)
            else:
                # Show winner text with celebration
                self._render_winner_text(buffer)
        else:
            # Not enough correct answers - show encouraging feedback
            draw_centered_text(buffer, "ХОРОШАЯ ПОПЫТКА!", 15, self._silver, scale=1)
            draw_centered_text(buffer, f"{self._score}/{len(self._questions)}", 40, self._silver, scale=2)
            pct = int(self._score / len(self._questions) * 100)
            draw_centered_text(buffer, f"{pct}%", 65, (150, 150, 180), scale=2)
            draw_centered_text(buffer, f"Нужно {FREE_COCKTAIL_THRESHOLD}+ для приза", 90, (120, 120, 140), scale=1)
            draw_centered_text(buffer, "Попробуй ещё!", 104, (100, 200, 100), scale=1)

            # Press to continue - blinking
            if int(self._time_in_phase / 500) % 2 == 0:
                draw_centered_text(buffer, "НАЖМИ КНОПКУ", 115, (100, 100, 120), scale=1)

    def _render_winner_text(self, buffer) -> None:
        """Render winner celebration text."""
        from artifact.graphics.text_utils import draw_centered_text

        pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 150)
        title_color = tuple(int(c * pulse) for c in self._gold)

        draw_centered_text(buffer, "ПОБЕДА!", 15, title_color, scale=2)
        draw_centered_text(buffer, f"{self._score}/{len(self._questions)}", 40, self._correct_green, scale=2)
        draw_centered_text(buffer, "БЕСПЛАТНЫЙ", 65, self._gold, scale=1)
        draw_centered_text(buffer, "КОКТЕЙЛЬ!", 80, self._gold, scale=2)
        draw_centered_text(buffer, "Покажи бармену", 100, (150, 200, 150), scale=1)

        # Press to continue
        if int(self._time_in_phase / 500) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ КНОПКУ", 115, (100, 100, 120), scale=1)

    def render_ticker(self, buffer) -> None:
        """Render ticker display."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, render_ticker_static, TickerEffect, TextEffect

        clear(buffer)

        if self.phase == ModePhase.INTRO:
            render_ticker_animated(
                buffer, f"ВИКТОРИНА - {FREE_COCKTAIL_THRESHOLD}+ ВЕРНО = КОКТЕЙЛЬ",
                self._time_in_phase, self._gold,
                TickerEffect.SPARKLE_SCROLL, speed=0.025
            )
        elif self.phase == ModePhase.ACTIVE:
            status = f"#{self._current_question + 1}/{self.QUESTIONS_PER_GAME} ВЕРНО:{self._score}"
            render_ticker_static(buffer, status, self._time_in_phase, self._gold, TextEffect.GLOW)
        elif self.phase == ModePhase.RESULT:
            if self._won_cocktail:
                render_ticker_animated(
                    buffer, "ПОБЕДА! БЕСПЛАТНЫЙ КОКТЕЙЛЬ!",
                    self._time_in_phase, self._correct_green,
                    TickerEffect.WAVE_SCROLL, speed=0.022
                )
            else:
                render_ticker_animated(
                    buffer, f"СЧЁТ {self._score}/{len(self._questions)} - ПОПРОБУЙ ЕЩЁ",
                    self._time_in_phase, self._silver,
                    TickerEffect.SCROLL, speed=0.022
                )

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        if self.phase == ModePhase.ACTIVE:
            time_left = int(self._time_remaining)
            return f"Q{self._current_question + 1} {time_left}s OK:{self._score}"[:16]
        elif self.phase == ModePhase.RESULT:
            if self._won_cocktail:
                return "КОКТЕЙЛЬ ТВОЙ!".center(16)
            else:
                return f"{self._score}/{len(self._questions)} TRY AGAIN".center(16)[:16]
        return " ВИКТОРИНА ".center(16)
