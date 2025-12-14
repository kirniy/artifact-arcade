"""Quiz mode - Who Wants to Be a Millionaire style.

Russian Gen-Z culture trivia with dramatic effects, sounds, and 4 answer options.
Styled after "Кто хочет стать миллионером" with prize ladder and lifelines.
"""

from typing import List, Tuple, Optional, Dict
import random
import math
import os

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem, ParticlePresets


# =============================================================================
# MASSIVE QUESTION DATABASE - Russian Gen-Z Culture, 2010s-2020s
# Format: (question, [option_A, option_B, option_C, option_D], correct_index 0-3)
# =============================================================================

QUIZ_QUESTIONS: List[Tuple[str, List[str], int]] = [
    # ===========================================================================
    # RUSSIAN RAP & HIP-HOP (50 questions)
    # ===========================================================================
    ("Кто из рэперов известен треком 'Патимейкер'?", ["Скриптонит", "Элджей", "Face", "Pharaoh"], 1),
    ("Настоящее имя Моргенштерна?", ["Алишер Валеев", "Алексей Лёхин", "Тимур Юнусов", "Мирон Фёдоров"], 0),
    ("Кто поёт 'Между нами тает лёд'?", ["Грибы", "Время и Стекло", "Gayazov$ Brother$", "Мот"], 0),
    ("Лейбл Скриптонита?", ["Gazgolder", "Black Star", "Booking Machine", "Ледяной"], 2),
    ("Кто записал 'Ратататата' с Моргенштерном?", ["Элджей", "Face", "OG Buda", "Слава КПСС"], 2),
    ("Город, откуда Скриптонит?", ["Москва", "Павлодар", "Санкт-Петербург", "Алматы"], 1),
    ("Альбом Oxxxymiron 2022?", ["Горгород", "Смутное время", "Красота и уродство", "Вечный жид"], 2),
    ("Кто из рэперов баттлился с Гнойным?", ["Oxxxymiron", "Noize MC", "Хаски", "Face"], 0),
    ("Первый альбом Pharaoh?", ["Фосфор", "Pink Phloyd", "Акид", "Холод"], 1),
    ("Основатель Black Star?", ["Тимати", "Баста", "L'One", "Мот"], 0),
    ("Кто спел 'Минимал'?", ["Элджей", "Feduk", "Ramil'", "Jah Khalib"], 0),
    ("Дуэт 'Грибы' из какой страны?", ["Россия", "Украина", "Беларусь", "Казахстан"], 1),
    ("Имя Басты?", ["Василий Вакуленко", "Кирилл Толмацкий", "Дмитрий Кузнецов", "Алексей Узенюк"], 0),
    ("Кто поёт 'Пьяный туман'?", ["Мот", "Jah Khalib", "Ёлка", "Макс Корж"], 3),
    ("Проект 'Andy Panda' это..?", ["Элджей", "Скриптонит", "Feduk", "Big Baby Tape"], 0),
    ("Рэпер, известный фразой 'Йоу, это Пушка'?", ["Lil Pump", "Big Baby Tape", "OG Buda", "Платина"], 1),
    ("Автор трека 'Медуза'?", ["Matrang", "Jony", "Rauf & Faik", "HammAli & Navai"], 0),
    ("Кто из рэперов снимался в 'Холоп'?", ["Тимати", "Элджей", "Милохин", "Моргенштерн"], 2),
    ("Трек 'Розовое вино' чей?", ["Элджей и Feduk", "Тима Белорусских", "Jony", "Rauf & Faik"], 0),
    ("Баста - это псевдоним или настоящее имя?", ["Псевдоним", "Настоящее", "Отчество", "Прозвище"], 0),
    ("Кто записал 'Космос'?", ["Хаски", "Скриптонит", "Oxxxymiron", "Pharaoh"], 1),
    ("Клип на какой трек снят в стиле GTA?", ["Cadillac", "Рататата", "YUMMY", "360°"], 0),
    ("Рэпер из дуэта 2 Маши?", ["Маша Вебер", "Надя Дорофеева", "Это не рэп", "Аня Покров"], 2),
    ("Кто из рэперов учился на журналиста?", ["Oxxxymiron", "Скриптонит", "Noize MC", "Баста"], 0),
    ("Город Oxxxymiron?", ["Москва", "Лондон", "Санкт-Петербург", "Ростов"], 2),
    ("Первый хит Face?", ["Бургер", "Гоша Рубчинский", "Юморист", "Мой калашников"], 0),
    ("Лейбл Gazgolder основал?", ["Тимати", "Баста", "Скриптонит", "Гуф"], 1),
    ("Кто записал 'Тает лёд' ремикс с Моргенштерном?", ["Грибы", "Время и стекло", "Никто", "Jah Khalib"], 2),
    ("Автор 'Малый повзрослел'?", ["Скриптонит", "104", "Lizer", "OBLADAET"], 1),
    ("Трек 'Лампочки' спел?", ["GSPD", "Дора", "Rakhim", "Mayot"], 0),
    ("Кто автор 'Привет, как дела'?", ["Jony", "Rauf & Faik", "HammAli", "Ramil'"], 0),
    ("Сколько лет Моргенштерн получил условно в 2021?", ["0", "1", "2", "Штраф"], 3),
    ("Альбом 'Горгород' - это..?", ["Рэп-опера", "Микстейп", "EP", "Сингл"], 0),
    ("Кто из рэперов - сын Децла?", ["Никто", "LJ", "Кравц", "Скриптонит"], 0),
    ("Трек 'Девочка с каре' исполняет?", ["Мукка", "Lizer", "GSPD", "Tima Belorusskih"], 0),
    ("Известный баттл рэп-площадка?", ["Versus", "Rap.ru", "HipHop.ru", "Рифмы и Панчи"], 0),
    ("Pharaoh & Boulevard Depo это?", ["Dead Dynasty", "Booking Machine", "Gazgolder", "Black Star"], 0),
    ("Кто записал 'Дико тусим'?", ["GSPD", "Feduk", "Big Baby Tape", "SALUKI"], 2),
    ("Лейбл ATL принадлежит?", ["Никому", "Атланте", "Oxxxymiron", "ATL рэперу"], 3),
    ("Хаски из какого города?", ["Улан-Удэ", "Москва", "Питер", "Новосибирск"], 0),
    ("Кто снял клип 'Цвет настроения чёрный'?", ["Егор Крид", "Тимати", "Филипп Киркоров", "Оба"], 3),
    ("Mayot известен треком?", ["Горы", "Море", "Небо", "Луна"], 0),
    ("Кто из рэперов вёл 'Антихайп'?", ["Гнойный", "Замай", "Хованский", "Все трое"], 3),
    ("Первое появление Моргенштерна?", ["YouTube", "TikTok", "VK", "Instagram"], 0),
    ("Кто такой Слава КПСС?", ["Рэпер", "Политик", "Блогер", "Всё сразу"], 3),
    ("Трек 'Ultimo Papa' чей?", ["Платина", "Big Baby Tape", "Boulevard Depo", "SALUKI"], 0),
    ("Kizaru это?", ["Продюсер", "Рэпер", "DJ", "Рэпер и продюсер"], 3),
    ("Автор 'Поколение'?", ["Тима Белорусских", "Jah Khalib", "Макс Корж", "Мот"], 0),
    ("Альбом '17' выпустил?", ["XXXTentacion", "Lil Peep", "Pharaoh", "Все трое"], 0),
    ("Кто такой Thomas Mraz?", ["Продюсер ATL", "Рэпер", "Битмейкер", "Всё верно"], 0),

    # ===========================================================================
    # MEMES & INTERNET CULTURE (40 questions)
    # ===========================================================================
    ("Откуда фраза 'Это фиаско братан'?", ["ТикТок", "Ютуб", "ВК", "Двач"], 1),
    ("'Окей бумер' это ответ кому?", ["Молодым", "Старшим", "Ровесникам", "Всем"], 1),
    ("Что значит 'краш'?", ["Враг", "Объект симпатии", "Друг", "Родитель"], 1),
    ("Что такое 'рофл'?", ["Шутка", "Обида", "Ссора", "Совет"], 0),
    ("Флексить означает?", ["Грустить", "Хвастаться", "Работать", "Спать"], 1),
    ("Кринж это?", ["Круто", "Стыдно", "Смешно", "Грустно"], 1),
    ("Что значит 'чилить'?", ["Работать", "Отдыхать", "Бегать", "Есть"], 1),
    ("Вайб это?", ["Музыка", "Атмосфера", "Еда", "Одежда"], 1),
    ("Токсик это?", ["Добрый человек", "Вредный человек", "Весёлый", "Тихий"], 1),
    ("Хейтер это?", ["Фанат", "Ненавистник", "Друг", "Коллега"], 1),
    ("Зумер это поколение?", ["X", "Y", "Z", "Бумеров"], 2),
    ("Что значит 'изи'?", ["Сложно", "Легко", "Быстро", "Медленно"], 1),
    ("Рандом означает?", ["Плановый", "Случайный", "Красивый", "Старый"], 1),
    ("Что такое 'агриться'?", ["Радоваться", "Злиться", "Смеяться", "Плакать"], 1),
    ("Мем 'Ждун' откуда?", ["Россия", "Голландия", "США", "Япония"], 1),
    ("'Не баг а фича' из какой сферы?", ["Музыка", "IT", "Спорт", "Кино"], 1),
    ("Что значит 'войсить'?", ["Писать", "Звонить", "Отправлять голосовые", "Молчать"], 2),
    ("Стримить это?", ["Смотреть", "Транслировать", "Скачивать", "Удалять"], 1),
    ("Донатить значит?", ["Брать", "Жертвовать", "Красть", "Копить"], 1),
    ("Что такое 'пруф'?", ["Ложь", "Доказательство", "Шутка", "Мем"], 1),
    ("Фейк это?", ["Правда", "Подделка", "Новость", "Фото"], 1),
    ("Абьюз это?", ["Любовь", "Насилие", "Дружба", "Работа"], 1),
    ("Что значит 'шипперить'?", ["Отправлять", "Объединять в пару", "Разлучать", "Игнорить"], 1),
    ("ОТП расшифровывается как?", ["One True Pairing", "Only The Best", "Open Top", "Other"], 0),
    ("Мем с котом и салатом называется?", ["Женщина кричит на кота", "Кот и овощи", "Сердитый кот", "Нян кэт"], 0),
    ("'Press F' означает?", ["Победу", "Уважение/скорбь", "Радость", "Злость"], 1),
    ("Что такое 'угарать'?", ["Плакать", "Смеяться", "Спать", "Есть"], 1),
    ("Зашквар это?", ["Круто", "Позор", "Победа", "Подарок"], 1),
    ("ЧСВ расшифровывается как?", ["Чувство собственной важности", "Часы", "Число", "Частота"], 0),
    ("Лойс это?", ["Дизлайк", "Лайк", "Коммент", "Репост"], 1),
    ("Что такое 'хайп'?", ["Тишина", "Шумиха", "Грусть", "Сон"], 1),
    ("Фраза 'го' означает?", ["Стой", "Пойдём", "Сиди", "Спи"], 1),
    ("Что такое 'сасный'?", ["Некрасивый", "Привлекательный", "Злой", "Глупый"], 1),
    ("ЛП это?", ["Лучшая подруга", "Любимый парень", "Левый поворот", "Литр пива"], 0),
    ("Тян это?", ["Парень", "Девушка", "Ребёнок", "Старик"], 1),
    ("Кун это?", ["Девушка", "Парень", "Ребёнок", "Животное"], 1),
    ("Что значит 'орать'?", ["Кричать", "Сильно смеяться", "Плакать", "Петь"], 1),
    ("Рил это?", ["Фейк", "По-настоящему", "Шутка", "Мем"], 1),
    ("Имба означает?", ["Слабый", "Имбалансный/сильный", "Красивый", "Старый"], 1),
    ("Нуб это?", ["Профи", "Новичок", "Читер", "Админ"], 1),

    # ===========================================================================
    # YOUTUBE & STREAMING (35 questions)
    # ===========================================================================
    ("Самый популярный русский ютубер?", ["А4", "Моргенштерн", "Дудь", "BadComedian"], 0),
    ("Кто ведёт 'вДудь'?", ["Юрий Дудь", "Ивангай", "Хованский", "Поперечный"], 0),
    ("Канал BadComedian про что?", ["Игры", "Кино", "Музыка", "Еда"], 1),
    ("Кто такой А4?", ["Влад Бумага", "Лист бумаги", "Формат", "Принтер"], 0),
    ("Первый русский ютубер с 10М подписчиков?", ["А4", "Ивангай", "Марьяна Ро", "Хованский"], 1),
    ("Канал 'This is Хорошо' вёл?", ["Стас Давыдов", "Макс +100500", "Ивангай", "Соболев"], 0),
    ("Проект 'Что было дальше' на каком канале?", ["LABELCOM", "Stand-Up Club", "ТНТ", "СТС"], 0),
    ("Кто создал 'Утренний курьер'?", ["Литвин", "Mellstroy", "А4", "Моргенштерн"], 0),
    ("Первое шоу Юрия Дудя?", ["Versus", "вДудь", "Поехавший", "Другое"], 0),
    ("Канал Wylsacom про что?", ["Еда", "Техника", "Игры", "Музыка"], 1),
    ("Кто такой Kuplinov?", ["Летсплейщик", "Рэпер", "Повар", "Спортсмен"], 0),
    ("Канал 'Трансформатор' вёл?", ["Портнягин", "Дудь", "Соболев", "Хайп"], 0),
    ("Булкин делает видео про?", ["Машины", "Игры", "Еду", "Музыку"], 0),
    ("Кто такой Поззи?", ["Футболист-ютубер", "Рэпер", "Актёр", "Геймер"], 0),
    ("Канал 'Редакция' это?", ["Новости", "Игры", "Музыка", "Еда"], 0),
    ("Кто ведёт 'Осторожно: Собчак'?", ["Ксения Собчак", "Дудь", "Ивлеева", "Бузова"], 0),
    ("'Пушка' - шоу на канале?", ["Labelcom", "Caramba TV", "ТНТ", "Первый"], 0),
    ("Кто создал 'Чикен Карри'?", ["Соболев", "Поперечный", "Дудь", "Долгополов"], 0),
    ("Канал 'Парфёнон' про что?", ["Историю", "Спорт", "Музыку", "Игры"], 0),
    ("Кто такой Druzhko?", ["Ведущий", "Рэпер", "Геймер", "Спортсмен"], 0),
    ("Mellstroy это?", ["Стример", "Рэпер", "Актёр", "Спортсмен"], 0),
    ("Влад А4 из какой страны?", ["Россия", "Беларусь", "Украина", "Казахстан"], 1),
    ("Шоу 'Что было дальше' про?", ["Истории", "Музыку", "Спорт", "Еду"], 0),
    ("Кто такой Гурам?", ["Боец ММА", "Рэпер", "Блогер", "Всё верно"], 3),
    ("Канал Литвина про?", ["Розыгрыши", "Музыку", "Спорт", "Новости"], 0),
    ("Кто такой Славный Друже?", ["Обзорщик еды", "Геймер", "Рэпер", "Актёр"], 0),
    ("'Антон тут рядом' это?", ["Фонд", "Канал", "Фильм", "Песня"], 0),
    ("Канал Ильи Варламова про?", ["Урбанистику", "Еду", "Игры", "Музыку"], 0),
    ("Шоу 'Подкаст' у кого?", ["Дудя", "Собчак", "Многих", "Никого"], 2),
    ("Первый канал с 50М подписчиков из СНГ?", ["А4", "Ивангай", "Like Nastya", "Моргенштерн"], 2),
    ("Кто такой ДЖАРАХОВ?", ["Блогер", "Рэпер", "Оба", "Ни то ни другое"], 2),
    ("Caramba TV это?", ["Stand-Up канал", "Игровой канал", "Музыкальный", "Новостной"], 0),
    ("Первое интервью Дудя с Бастой вышло когда?", ["2017", "2018", "2019", "2020"], 0),
    ("Канал 'The Люди' про?", ["Интервью", "Игры", "Музыку", "Еду"], 0),
    ("Кто ведёт 'Comment Out'?", ["Гудков и Харламов", "Дудь", "Поперечный", "Соболев"], 0),

    # ===========================================================================
    # TIKTOK & SHORT VIDEO (25 questions)
    # ===========================================================================
    ("Самый популярный русский тиктокер?", ["Милохин", "Покров", "Хабиб", "Валя Карнавал"], 0),
    ("Даня Милохин из какого шоу?", ["Дом-2", "Холостяк", "Ледниковый период", "Звёзды в Африке"], 2),
    ("Что такое 'попасть в рекомендации'?", ["Удалиться", "Стать вирусным", "Заблокироваться", "Выйти"], 1),
    ("Дуэт в ТикТоке это?", ["Видео с другим человеком", "Песня", "Танец", "Фильтр"], 0),
    ("Что значит 'залететь'?", ["Упасть", "Стать популярным", "Удалиться", "Выйти"], 1),
    ("Хештег #fyp означает?", ["For You Page", "Free Your Phone", "Fun Year Party", "Fake"], 0),
    ("Кто такая Валя Карнавал?", ["Тиктокерша", "Рэперша", "Актриса", "Всё верно"], 0),
    ("Сколько секунд был макс. ТикТок в 2020?", ["15", "30", "60", "180"], 2),
    ("Тренд 'Silhouette Challenge' про что?", ["Танец-силуэт", "Пение", "Готовку", "Спорт"], 0),
    ("Что такое 'дуэтнуться'?", ["Спеть вместе", "Снять дуэт", "Подраться", "Помириться"], 1),
    ("POV расшифровывается как?", ["Point of View", "Person Over Video", "Play Our Video", "Post"], 0),
    ("Тренд 'Буба' это?", ["Танец", "Песня", "Мем", "Фильтр"], 1),
    ("Сколько подписчиков у Хабиба Нурмагомедова?", ["1М", "10М", "30М+", "100М"], 2),
    ("Кто такой Юрий Кузнецов (ТикТок)?", ["Повар", "Дальнобойщик", "Рэпер", "Актёр"], 1),
    ("Что такое 'стич'?", ["Ответ на видео", "Удаление", "Блок", "Лайк"], 0),
    ("Трендовый звук это?", ["Популярная аудиодорожка", "Тишина", "Шум", "Музыка"], 0),
    ("Кто придумал 'Буба'?", ["Bayamaka", "Моргенштерн", "Милохин", "Покров"], 0),
    ("Что такое 'теневой бан'?", ["Скрытое ограничение", "Удаление", "Блокировка", "Повышение"], 0),
    ("Максимальное время ТикТока сейчас?", ["1 мин", "3 мин", "10 мин", "Без лимита"], 2),
    ("Грин-скрин в ТикТоке для чего?", ["Замена фона", "Замена лица", "Удаление видео", "Музыки"], 0),
    ("Кто такой @the_kolya?", ["Блогер-комик", "Рэпер", "Актёр", "Спортсмен"], 0),
    ("Что означает 'вайнить'?", ["Снимать короткие видео", "Пить вино", "Плакать", "Спать"], 0),
    ("'Ищу связь' это тренд про?", ["Знакомства", "Интернет", "Работу", "Деньги"], 0),
    ("Кто такая Дина Саева?", ["Тиктокерша", "Рэперша", "Актриса", "Модель"], 0),
    ("Лайки в ТикТоке называются?", ["Сердечки", "Лойсы", "Плюсы", "Звёзды"], 0),

    # ===========================================================================
    # TV SHOWS & SERIES (30 questions)
    # ===========================================================================
    ("Русский сериал про 90-е от Netflix?", ["Лето", "Топи", "Содержанки", "Слово пацана"], 3),
    ("'Эпидемия' снята по книге?", ["Вонгозеро", "Метро", "Москва 2042", "Пикник"], 0),
    ("Сериал 'Мажор' про кого?", ["Полицейского", "Врача", "Учителя", "Бизнесмена"], 0),
    ("Кто играет главную роль в 'Слово пацана'?", ["Леон Кемстач", "Иван Янковский", "Данила Козловский", "Другой"], 1),
    ("Шоу 'Маска' на каком канале?", ["НТВ", "Первый", "СТС", "ТНТ"], 0),
    ("Ведущий шоу 'Голос'?", ["Нагиев", "Меладзе", "Градский", "Меняется"], 3),
    ("Сериал 'Кухня' про что?", ["Ресторан", "Больницу", "Полицию", "Школу"], 0),
    ("'Физрук' с каким актёром?", ["Нагиев", "Галустян", "Харламов", "Светлаков"], 0),
    ("Канал сериала 'Реальные пацаны'?", ["ТНТ", "СТС", "Первый", "НТВ"], 0),
    ("'Интерны' снимали сколько сезонов?", ["7", "10", "14", "20"], 2),
    ("'Склифосовский' это сериал про?", ["Врачей", "Полицию", "Школу", "Армию"], 0),
    ("Шоу 'Камеди Клаб' на каком канале?", ["ТНТ", "СТС", "Первый", "Россия 1"], 0),
    ("Кто создал 'Камеди Клаб'?", ["Мартиросян и Незлобин", "Галустян", "Харламов", "Нагиев"], 0),
    ("'Холоп' это?", ["Фильм", "Сериал", "Шоу", "Мультфильм"], 0),
    ("Режиссёр 'Холоп'?", ["Клим Шипенко", "Бекмамбетов", "Бондарчук", "Сарик Андреасян"], 0),
    ("Шоу 'Импровизация' ведут?", ["Попов, Шастун, Матвиенко, Позов", "Харламов", "Галустян", "Нагиев"], 0),
    ("'Полицейский с Рублёвки' с кем?", ["Бурунов", "Нагиев", "Харламов", "Козловский"], 0),
    ("Сериал 'Чики' про?", ["Провинциальный стриптиз", "Ресторан", "Полицию", "Школу"], 0),
    ("'Триггер' это сериал про?", ["Психолога", "Полицейского", "Врача", "Учителя"], 0),
    ("Канал шоу 'Секретный миллионер'?", ["Пятница", "ТНТ", "СТС", "НТВ"], 0),
    ("'Вампиры средней полосы' это?", ["Комедия", "Ужасы", "Драма", "Боевик"], 0),
    ("Шоу 'Орёл и решка' про?", ["Путешествия", "Еду", "Моду", "Спорт"], 0),
    ("'Содержанки' выходит на?", ["START", "Кинопоиск", "Netflix", "ivi"], 0),
    ("'Бывшие' на каком сервисе?", ["PREMIER", "Netflix", "Кинопоиск", "START"], 0),
    ("Шоу 'Танцы' на каком канале?", ["ТНТ", "СТС", "Первый", "Россия"], 0),
    ("'Перевал Дятлова' сняли на?", ["ТНТ", "Первый", "НТВ", "Россия"], 0),
    ("Сериал 'Фишер' про?", ["Маньяка", "Врача", "Полицию", "Школу"], 0),
    ("'Эпидемия' выходила на?", ["PREMIER", "Netflix", "Кинопоиск", "ivi"], 0),
    ("Шоу 'Форт Боярд' русская версия на?", ["СТС", "Первый", "ТНТ", "НТВ"], 1),
    ("'Пищеблок' это сериал про?", ["Пионерлагерь с вампирами", "Ресторан", "Больницу", "Школу"], 0),

    # ===========================================================================
    # GAMING (30 questions)
    # ===========================================================================
    ("Самая популярная игра в мире 2023?", ["Minecraft", "Fortnite", "GTA V", "Roblox"], 0),
    ("PUBG расшифровывается как?", ["PlayerUnknown's Battlegrounds", "Play Until Battle Ground", "Personal", "Другое"], 0),
    ("Первая королевская битва?", ["PUBG", "Fortnite", "H1Z1", "ARMA мод"], 3),
    ("Кто создал Minecraft?", ["Notch", "Gaben", "Kojima", "Todd Howard"], 0),
    ("GTA V вышла в каком году?", ["2011", "2013", "2015", "2017"], 1),
    ("Валорант от какой компании?", ["Riot Games", "Valve", "Blizzard", "EA"], 0),
    ("CS:GO стал бесплатным в?", ["2017", "2018", "2019", "Всегда был"], 1),
    ("Dota 2 от какой компании?", ["Valve", "Riot", "Blizzard", "EA"], 0),
    ("LoL расшифровывается как?", ["League of Legends", "Lord of Lands", "Love of Life", "Другое"], 0),
    ("Геншин Импакт откуда?", ["Китай", "Япония", "Корея", "США"], 0),
    ("Первый скин в Fortnite стоил?", ["$0", "$5", "$10", "$20"], 3),
    ("Кто такой s1mple?", ["Игрок CS", "Стример", "Рэпер", "Ютубер"], 0),
    ("Команда NAVI из какой страны?", ["Украина", "Россия", "Беларусь", "Казахстан"], 0),
    ("Among Us вышел в каком году?", ["2018", "2019", "2020", "2021"], 0),
    ("Fall Guys это?", ["Батл рояль", "Шутер", "RPG", "Гонки"], 0),
    ("Roblox это?", ["Платформа для игр", "Одна игра", "Сервис", "Магазин"], 0),
    ("Первый iPhone с Fortnite?", ["iPhone 6", "iPhone 7", "iPhone X", "iPhone 11"], 0),
    ("Cyberpunk 2077 от?", ["CD Projekt RED", "Rockstar", "Ubisoft", "EA"], 0),
    ("Элден Ринг от?", ["FromSoftware", "Rockstar", "Ubisoft", "CD Projekt"], 0),
    ("Хогвартс Легаси про?", ["Гарри Поттера", "Властелин Колец", "Марвел", "DC"], 0),
    ("Сколько стоит PS5 на старте?", ["$400", "$500", "$600", "$700"], 1),
    ("Steam от какой компании?", ["Valve", "Epic", "EA", "Ubisoft"], 0),
    ("Epic Games Store раздаёт игры?", ["Бесплатно каждую неделю", "Платно", "Иногда", "Никогда"], 0),
    ("Discord изначально для?", ["Геймеров", "Бизнеса", "Школы", "Музыкантов"], 0),
    ("Twitch принадлежит?", ["Amazon", "Google", "Microsoft", "Meta"], 0),
    ("Кто такой Братишкин?", ["Стример", "Рэпер", "Ютубер", "Тиктокер"], 0),
    ("Escape from Tarkov из?", ["России", "Украины", "США", "Германии"], 0),
    ("Standoff 2 это?", ["Мобильный CS", "Батл рояль", "RPG", "Гонки"], 0),
    ("Brawl Stars от?", ["Supercell", "Riot", "EA", "Ubisoft"], 0),
    ("Clash of Clans вышел в?", ["2012", "2013", "2014", "2015"], 0),

    # ===========================================================================
    # SLANG & LANGUAGE (20 questions)
    # ===========================================================================
    ("'Жиза' означает?", ["Ложь", "Жизненно", "Странно", "Грустно"], 1),
    ("'Душнила' это?", ["Весёлый", "Зануда", "Умный", "Глупый"], 1),
    ("'Падра' откуда?", ["Вписки", "Книг", "Фильмов", "Музыки"], 0),
    ("'ЛОЛ' означает?", ["Laughing Out Loud", "Lots of Love", "Другое", "League of Legends"], 0),
    ("'Сорян' это?", ["Привет", "Извини", "Пока", "Спасибо"], 1),
    ("'Чётко' означает?", ["Плохо", "Хорошо", "Странно", "Грустно"], 1),
    ("'Кекать' означает?", ["Плакать", "Смеяться", "Работать", "Спать"], 1),
    ("'Азаза' выражает?", ["Грусть", "Смех", "Злость", "Удивление"], 1),
    ("'Братан' это?", ["Враг", "Друг", "Коллега", "Родственник"], 1),
    ("'Чё как?' означает?", ["Пока", "Как дела?", "Извини", "Спасибо"], 1),
    ("'Топ' означает?", ["Плохо", "Лучшее", "Среднее", "Странное"], 1),
    ("'Мутить' означает?", ["Спать", "Организовывать", "Есть", "Пить"], 1),
    ("'Чилово' это?", ["Плохо", "Расслабленно", "Быстро", "Громко"], 1),
    ("'Агонь' означает?", ["Вода", "Огонь/круто", "Земля", "Воздух"], 1),
    ("'Бомбить' означает?", ["Радоваться", "Злиться", "Смеяться", "Плакать"], 1),
    ("'Забить' означает?", ["Помнить", "Забыть/игнорировать", "Делать", "Есть"], 1),
    ("'Зачётно' означает?", ["Плохо", "Хорошо", "Странно", "Грустно"], 1),
    ("'Кринжово' означает?", ["Круто", "Стыдно", "Весело", "Грустно"], 1),
    ("'Лютый' означает?", ["Слабый", "Сильный/крутой", "Маленький", "Большой"], 1),
    ("'Нормис' это?", ["Странный", "Обычный человек", "Крутой", "Богатый"], 1),
]


# Prize ladder (like WWTBAM)
PRIZE_LADDER = [
    100, 200, 300, 500, 1000,
    2000, 4000, 8000, 16000, 32000,
    64000, 125000, 250000, 500000, 1000000
]

# Safe havens (guaranteed amounts)
SAFE_HAVENS = {4: 1000, 9: 32000, 14: 1000000}


class QuizPhase:
    INTRO = "intro"
    QUESTION = "question"
    THINKING = "thinking"
    REVEAL = "reveal"
    CORRECT = "correct"
    WRONG = "wrong"
    RESULT = "result"


class QuizMode(BaseMode):
    """Quiz mode - Who Wants to Be a Millionaire style.

    Features:
    - 15 questions with increasing difficulty
    - Prize ladder with safe havens
    - 4 answer options (A, B, C, D)
    - Dramatic reveals and sound effects
    - Millionaire-style animations
    """

    name = "quiz"
    display_name = "МИЛЛИОНЕР"
    description = "Кто хочет стать миллионером?"
    icon = "?"
    style = "millionaire"
    requires_camera = False
    requires_ai = False
    estimated_duration = 180

    # Game settings
    QUESTIONS_PER_GAME = 10
    THINKING_TIME = 15.0  # seconds per question

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Game state
        self._questions: List[Tuple[str, List[str], int]] = []
        self._current_question: int = 0
        self._selected_answer: Optional[int] = None  # 0-3
        self._time_remaining: float = 0.0
        self._winnings: int = 0
        self._sub_phase = QuizPhase.INTRO

        # Animation state
        self._reveal_progress: float = 0.0
        self._flash_alpha: float = 0.0
        self._suspense_time: float = 0.0
        self._answer_locked: bool = False
        self._pulse_time: float = 0.0

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

        self._current_question = 0
        self._selected_answer = None
        self._time_remaining = self.THINKING_TIME
        self._winnings = 0
        self._sub_phase = QuizPhase.INTRO
        self._answer_locked = False
        self._reveal_progress = 0.0
        self._flash_alpha = 0.0
        self._suspense_time = 0.0
        self._pulse_time = 0.0

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

        if self.phase == ModePhase.INTRO:
            if self._time_in_phase > 3000:
                self._sub_phase = QuizPhase.QUESTION
                self.change_phase(ModePhase.ACTIVE)

        elif self.phase == ModePhase.ACTIVE:
            if self._sub_phase == QuizPhase.QUESTION:
                # Countdown
                if not self._answer_locked:
                    self._time_remaining -= delta_ms / 1000
                    if self._time_remaining <= 0:
                        # Time's up - wrong!
                        self._sub_phase = QuizPhase.WRONG
                        self._time_in_phase = 0

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
                        self._winnings = PRIZE_LADDER[min(self._current_question, len(PRIZE_LADDER) - 1)]
                        self._flash_alpha = 1.0
                        gold = self._particles.get_emitter("gold")
                        if gold:
                            gold.burst(50)
                    else:
                        self._sub_phase = QuizPhase.WRONG
                    self._time_in_phase = 0

            elif self._sub_phase == QuizPhase.CORRECT:
                if self._time_in_phase > 2000:
                    self._next_question()

            elif self._sub_phase == QuizPhase.WRONG:
                if self._time_in_phase > 2500:
                    self._finish_game()

        elif self.phase == ModePhase.RESULT:
            if self._time_in_phase > 15000:
                self._finish()

    def on_input(self, event: Event) -> bool:
        """Handle input - A/B on left, C/D on right, confirm with center."""
        if self.phase == ModePhase.ACTIVE and self._sub_phase == QuizPhase.QUESTION:
            if not self._answer_locked:
                # Navigate options: Left cycles A/B, Right cycles C/D
                if event.type == EventType.ARCADE_LEFT:
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

    def _finish_game(self) -> None:
        """End the game and show results."""
        self._sub_phase = QuizPhase.RESULT
        self.change_phase(ModePhase.RESULT)

    def on_exit(self) -> None:
        """Cleanup."""
        self._particles.clear_all()
        self.stop_animations()

    def _finish(self) -> None:
        """Complete the mode."""
        score = self._current_question
        total = len(self._questions)
        pct = int(score / total * 100) if total > 0 else 0

        # Format winnings with separators
        winnings_str = f"{self._winnings:,}".replace(",", " ")

        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=f"Выигрыш: {winnings_str} ₽",
            ticker_text=f"МИЛЛИОНЕР: {score}/{total} = {winnings_str}₽",
            lcd_text=f"{winnings_str}P".center(16),
            should_print=True,
            print_data={
                "score": score,
                "total": total,
                "winnings": self._winnings,
                "percentage": pct,
                "type": "millionaire"
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
        elif self.phase == ModePhase.RESULT:
            self._render_result(buffer)

        # Render particles
        self._particles.render(buffer)

        # Flash overlay
        if self._flash_alpha > 0:
            flash_color = tuple(int(255 * self._flash_alpha * 0.3) for _ in range(3))
            fill(buffer, flash_color)

    def _render_intro(self, buffer) -> None:
        """Render intro screen."""
        from artifact.graphics.text_utils import draw_centered_text

        # Pulsing title
        pulse = 0.8 + 0.2 * math.sin(self._time_in_phase / 200)
        title_color = tuple(int(c * pulse) for c in self._gold)

        draw_centered_text(buffer, "КТО ХОЧЕТ", 25, title_color, scale=1)
        draw_centered_text(buffer, "СТАТЬ", 42, title_color, scale=2)
        draw_centered_text(buffer, "МИЛЛИОНЕРОМ?", 65, title_color, scale=1)

        # Countdown
        countdown = max(0, 3 - int(self._time_in_phase / 1000))
        if countdown > 0:
            draw_centered_text(buffer, str(countdown), 95, self._silver, scale=2)
        else:
            draw_centered_text(buffer, "ПОЕХАЛИ!", 95, self._correct_green, scale=1)

    def _render_game(self, buffer) -> None:
        """Render active game."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text, wrap_text

        question = self._questions[self._current_question]
        q_text, options, correct = question

        # Question number and prize
        prize = PRIZE_LADDER[min(self._current_question, len(PRIZE_LADDER) - 1)]
        prize_str = f"{prize:,}".replace(",", " ")
        draw_centered_text(buffer, f"#{self._current_question + 1} за {prize_str}₽", 2, self._gold, scale=1)

        # Timer bar
        timer_pct = self._time_remaining / self.THINKING_TIME
        timer_w = int(120 * timer_pct)
        timer_color = self._correct_green if timer_pct > 0.3 else self._wrong_red
        draw_rect(buffer, 4, 12, 120, 3, (40, 40, 60))
        if timer_w > 0:
            draw_rect(buffer, 4, 12, timer_w, 3, timer_color)

        # Question text (wrapped)
        lines = wrap_text(q_text, 20)
        y = 20
        for line in lines[:2]:
            draw_centered_text(buffer, line, y, (255, 255, 255), scale=1)
            y += 11

        # Answer options in 2x2 grid
        option_labels = ["A", "B", "C", "D"]
        positions = [(2, 48), (66, 48), (2, 78), (66, 78)]  # x, y for each option

        for i, (opt, label) in enumerate(zip(options, option_labels)):
            x, y = positions[i]
            w, h = 60, 26

            # Determine color based on state
            if self._sub_phase == QuizPhase.REVEAL or self._sub_phase in (QuizPhase.CORRECT, QuizPhase.WRONG):
                if i == correct:
                    color = self._correct_green
                elif i == self._selected_answer and i != correct:
                    color = self._wrong_red
                else:
                    color = self._option_blue
            elif i == self._selected_answer:
                # Pulsing selection
                pulse = 0.7 + 0.3 * math.sin(self._pulse_time / 100)
                color = tuple(int(c * pulse) for c in self._option_selected)
            else:
                color = self._option_blue

            # Draw option box
            draw_rect(buffer, x, y, w, h, color)

            # Option text - truncate if needed
            display_text = f"{label}:{opt}"
            if len(display_text) > 9:
                display_text = display_text[:8] + "…"
            draw_centered_text(buffer, display_text, y + 9, (255, 255, 255), scale=1)

        # Instructions at bottom
        if self._sub_phase == QuizPhase.QUESTION and not self._answer_locked:
            draw_centered_text(buffer, "< A/B  C/D >  OK", 118, (100, 120, 150), scale=1)
        elif self._sub_phase == QuizPhase.THINKING:
            dots = "." * (int(self._suspense_time / 300) % 4)
            draw_centered_text(buffer, f"ДУМАЕМ{dots}", 118, self._gold, scale=1)

    def _render_result(self, buffer) -> None:
        """Render final result."""
        from artifact.graphics.text_utils import draw_centered_text

        # Title
        draw_centered_text(buffer, "ИГРА ОКОНЧЕНА", 10, self._gold, scale=1)

        # Score
        draw_centered_text(buffer, f"{self._current_question}/{len(self._questions)}", 35, self._silver, scale=2)

        # Winnings
        winnings_str = f"{self._winnings:,}".replace(",", " ")
        draw_centered_text(buffer, "ВЫИГРЫШ:", 60, (150, 150, 180), scale=1)
        draw_centered_text(buffer, f"{winnings_str} P", 78, self._gold, scale=2)

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
                buffer, "КТО ХОЧЕТ СТАТЬ МИЛЛИОНЕРОМ",
                self._time_in_phase, self._gold,
                TickerEffect.RAINBOW_SCROLL, speed=0.025
            )
        elif self.phase == ModePhase.ACTIVE:
            prize = PRIZE_LADDER[min(self._current_question, len(PRIZE_LADDER) - 1)]
            prize_str = f"{prize:,}".replace(",", " ")
            status = f"#{self._current_question + 1} {prize_str}P"
            render_ticker_static(buffer, status, self._time_in_phase, self._gold, TextEffect.GLOW)
        elif self.phase == ModePhase.RESULT:
            winnings_str = f"{self._winnings:,}".replace(",", " ")
            render_ticker_animated(
                buffer, f"ВЫИГРЫШ {winnings_str} РУБЛЕЙ",
                self._time_in_phase, self._gold,
                TickerEffect.WAVE_SCROLL, speed=0.022
            )

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        if self.phase == ModePhase.ACTIVE:
            prize = PRIZE_LADDER[min(self._current_question, len(PRIZE_LADDER) - 1)]
            time_left = int(self._time_remaining)
            return f"Q{self._current_question + 1} {time_left}s {prize}P"[:16]
        elif self.phase == ModePhase.RESULT:
            return f"ВЫИГРЫШ {self._winnings}P"[:16].center(16)
        return " МИЛЛИОНЕР ".center(16)
