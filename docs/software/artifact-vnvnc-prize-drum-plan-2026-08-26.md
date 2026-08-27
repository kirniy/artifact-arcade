# ФОТОБУДКА ВИНОВНИЦЫ: физический призовой барабан

Дата спецификации: 26 августа 2026
Статус: локальный vertical slice и production-safety fixes реализованы; автоматические тесты зелёные; physical canary и production не запускались

## 1. Зафиксированное решение

В ФОТОБУДКА ВИНОВНИЦЫ появляется скрытый эксклюзивный режим физического колеса фортуны в форме вертикального барабана.

- Вход: удержание `9` на нумпаде 2,0 секунды.
- Выход: повторное удержание `9` 2,0 секунды.
- Режим не появляется в обычном меню фотобудки.
- Вход разрешён только из безопасного idle/menu состояния.
- Если выход запрошен во время выдачи или печати, режим сначала надёжно завершает транзакцию и лишь затем возвращается назад.
- Telegram-flow выбран по умолчанию при первом входе в режим.
- `6` — абсолютный выбор режима «без авторизации»; выбор сохраняется между гостями, пока его не изменят.
- `4` — абсолютный возврат в Telegram-flow; выбор также сохраняется между гостями.
- Большая кнопка — подтвердить, запустить барабан, перейти дальше.
- Базовый спин не требует Telegram и не имеет глобального программного лимита на человека: поток физически контролирует сотрудник.
- Telegram identity всегда session-scoped: после выдачи всех доступных призов и фиксации результата текущий пользователь отвязывается, одноразовый login token закрывается, а имя/avatar/ID удаляются из памяти машины. Приз остаётся в его сундуке. Если сохранён Telegram-flow, следующему гостю создаются новая login-сессия и новый QR.

Матрица спинов:

| Сценарий | Доступно |
|---|---:|
| Без Telegram | 1 базовый спин |
| Telegram подключён, активного буста нет | 1 базовый спин |
| Telegram подключён, подтверждён 1 активный буст VNVNC-канала | 1 базовый + 1 бонусный спин |
| Telegram подключён, подтверждены 2 или больше активных бустов | 1 базовый + 2 бонусных спина |

Авторизация сама по себе не выдаёт дополнительный спин. Число бонусных kiosk-спинов равно числу активных бустов, но ограничено двумя за клубную ночь: `bonus_spins = min(active_boosts, 2)`.

### Текущее доказанное состояние

- режим собран локально за feature flag и не включён на ФОТОБУДКА ВИНОВНИЦЫ;
- неоднозначный timeout после server commit сохраняет тот же `session_id + request_id`; повтор получает тот же неизменяемый award и не расходует второй приз;
- полный официальный Telegram OIDC/PKCE URL, включая `telegram:bot_access`, хранится только на backend; ФОТОБУДКА ВИНОВНИЦЫ получает 45-символьный opaque pairing URL, который кодируется в почти полноэкранный EC-Q v4 QR `123×123` с 3×3 LED-пикселями на модуль и 12-пиксельной quiet zone;
- RP80 выбирается автоматически только по VID:PID `0fe6:811e`; label-принтер IP-802 `353d:1249` и generic `ARTIFACT_PRINTER_PORT` отвергаются;
- ordinary receipt не показывает ложный блок `ДАТЫ ПРОХОДА`; он разрешён только для `TIX1FREE`;
- локально повторно пройдено 87 prize-drum/canary/receipt/device-detection тестов, включая переход main-screen/camera без чёрного кадра, randomized circular-reel invariants, signed loopback HTTP transport и явную `TEST`-маркировку canary на всех экранах/чеке;
- широкий photobooth/theme/ticker/schedule прогон даёт 56 pass; три устаревших ожидания `2k17-only` синхронизированы с каноническим default profile `brainrot,wedding,whatsapp`, не меняя production behavior;
- полный `modular-arcade` test suite даёт 150 pass; единственный noise — два уже существовавших Pillow deprecation warnings в `photobooth.py`;
- backend профиль вместе с безопасным policy configurator даёт 170 pass;
- авторизованная выдача в той же транзакции создаёт ровно один durable user-notification; guest не создаёт его; ошибка Telegram возвращает запись в pending, а сообщение содержит prize, code, expiry/две даты проходки, сундук и точную ссылку обычного колеса;
- отдельный preflight soak провёл 20 Telegram-сессий × 3 спина: 60 уникальных awards, 60 RP80 mock print jobs, idempotent retry каждого spin, ноль duplicate issue/code/print и ноль `PRINT_ERROR`;
- отдельный scanner race запускает два одновременных redeem через независимые DB-сессии и доказывает ровно один success, один `ALREADY_REDEEMED` и одного записанного staff ID;
- реальный renderer/state machine записан воспроизводимым скриптом в `output/prize-drum-motion-preview.mp4`: H.264, 768×768, 30 fps, 15,30 s; prize-only READY → server-confirmed 10,8-секундный spin → braking/reveal → result, `blackdetect` не нашёл ни одного black interval;
- QR из preview декодируются в точные payload; остаются обязательные скан с реального 3-мм LED panel и скан обоих QR с термобумаги.

## 2. Каталог и независимые лимиты

Источник выдачи: `ARTIFACT_KIOSK`.

Первоначальный kiosk-каталог:

| ID | Текст на барабане | Redemption |
|---|---|---|
| `COCKTL` | БЕСПЛАТНЫЙ КОКТЕЙЛЬ | staff scanner |
| `DEP1K` | ДЕПОЗИТ 1 000 ₽ | staff scanner |
| `DEP2K` | ДЕПОЗИТ 2 000 ₽ | staff scanner |
| `MERCHFREE` | БЕСПЛАТНЫЙ МЕРЧ | staff scanner |
| `SHOTFR` | БЕСПЛАТНЫЙ СЕТ ШОТОВ | staff scanner |
| `TIX1FREE` | БИЛЕТ НА ОДНОГО | существующий канонический приз бота |

Последнее уточнение о проходке трактуется как включение существующего `TIX1FREE`, а не создание нового типа приза. Перед production необходимо зафиксировать конкретный состав бесплатного мерча и количество шотов в сете — этот текст попадёт в scanner и чек.

Киоск использует собственную таблицу политик:

- свои веса;
- свои nightly/total limits;
- свои остатки;
- свои счётчики базовых и boost-спинов;
- свои включённые/выключенные призы.

Эти показатели не читают и не изменяют веса, остатки, кулдауны или `BoostSpinUsage` обычного Telegram-колеса. Общими остаются канонические определения призов, пользовательский сундук, `Coupon`, staff scanner и redemption audit trail.

Точные веса и лимиты не копируются из обычного колеса и не угадываются: это отдельная операторская конфигурация, которая при отсутствии значений закрывается fail-closed.

## 3. Срок действия

Часовой пояс: `Europe/Moscow`. Граница клубной ночи уже канонически задана в VNVNC backend как 07:00.

Для всех обычных kiosk-призов:

```text
club_date = VisitCheckinService.club_visit_date(server_now)
expires_at = 07:00 MSK следующего календарного дня club_date
```

- в `06:59:59` приз действителен;
- в `07:00:00` уже истёк;
- это проверяет сервер и staff scanner, а не только текст интерфейса.

`TIX1FREE` повторно использует канонический приз «БИЛЕТ НА ОДНОГО»:

- окно — следующая полная датированная пара пятничной и субботней клубных ночей;
- если приз выпал уже во время пятничной или субботней ночи, обе даты относятся к следующему полному уикенду, чтобы обе заявленные опции оставались реальными;
- один человек;
- один успешный проход суммарно за обе ночи;
- первое атомарное погашение закрывает QR навсегда;
- повторный scan возвращает `ALREADY_REDEEMED`.

## 4. Telegram Login и сундук

### Официальный flow

Используется официальный Telegram Login OIDC Authorization Code Flow с PKCE для `@vnvncbattlebot`, а не доверие Telegram ID от киоска.

1. ФОТОБУДКА ВИНОВНИЦЫ создаёт серверную kiosk-сессию. Telegram-flow показан по умолчанию; `6` позволяет немедленно перейти в guest-flow.
2. Backend создаёт полный официальный OIDC URL, но сохраняет его server-side; киоску возвращается только `https://api.vnvnc.ru/k/<128-bit-token>` с TTL 5 минут.
3. ФОТОБУДКА ВИНОВНИЦЫ показывает короткий pairing URL как QR с Telegram-иконкой в центре и минимум 2×2 физических LED-пикселя на модуль.
4. Телефон открывает `/k/{pairing_id}`; endpoint проверяет pending attempt, TTL и открытую Telegram-сессию, затем без потребления token делает no-store redirect в `https://oauth.telegram.org/auth`.
5. Запрашиваются только `openid profile telegram:bot_access`; телефон не запрашивается.
6. Callback серверно меняет `code` на токены с PKCE.
7. Backend проверяет подпись JWT по Telegram JWKS, `iss`, `aud`, `exp`, `state` и `nonce`.
8. Проверенный Telegram `id` связывается с существующим пользователем VNVNC и kiosk-сессией.
9. ФОТОБУДКА ВИНОВНИЦЫ видит статус через polling; все призы этой сессии появляются в обычном сундуке пользователя.
10. `telegram:bot_access` позволяет тому же боту отправить пользователю карточку выигрыша.
11. Когда BASE и возможный BOOST_BONUS завершены и issues надёжно сохранены, backend закрывает pairing, ФОТОБУДКА ВИНОВНИЦЫ очищает пользовательские данные и создаёт чистую сессию для следующего гостя.

Allowed URLs и callback регистрируются в BotFather. Client secret хранится только на backend и никогда не попадает на Raspberry Pi или в репозиторий.

Официальная документация: <https://core.telegram.org/bots/telegram-login>

### Буст канала

После OIDC backend вызывает уже существующий `ChannelBoostService.get_user_boost_info()`, который использует официальный Bot API `getUserChatBoosts`.

- бот должен оставаться администратором VNVNC-канала;
- `active_boosts` даёт `min(active_boosts, 2)` kiosk bonus allowances;
- отсутствие буста не блокирует базовый спин;
- ошибка Telegram API не выдаёт бонус, но позволяет повторить проверку;
- каждый бонус списывается только в одной транзакции с успешной выдачей соответствующего дополнительного приза;
- уникальность: `(source, telegram_id, club_night_date, BOOST, bonus_ordinal)`, где `bonus_ordinal ∈ {1, 2}`.

На странице телефона после входа показывается кнопка `БУСТНУТЬ КАНАЛ`, ведущая на канонический `https://t.me/boost/vnvnc_spb`. Backend повторно проверяет активные бусты непосредственно при каждом server-authoritative spin; `6` остаётся только абсолютным выбором guest-flow и не получает второй скрытой семантики.

## 5. Server-authoritative контракт

Клиент никогда не выбирает приз, coupon code, expiry, source или Telegram ID.

### Хранилище

- `artifact_kiosk_sessions`
  - session UUID, device, club night, выбранный auth-flow, paired user, status и число использованных session spins;
- `artifact_kiosk_prize_policies`
  - kiosk-only enabled flag, weight, nightly/total limits, awarded total и обязательное operator approval;
- `artifact_kiosk_user_nights`
  - отдельный от обычного колеса счётчик `used_count` на Telegram user/club night и последний проверенный boost state;
- `artifact_kiosk_awards`
  - session, canonical `Spin`/`Coupon`, `BASE|BOOST|GUEST`, timestamps, expiry policy и unique device request ID;
- `artifact_kiosk_oidc_attempts`
  - hashed state, nonce, PKCE verifier, server-only provider authorization URL, 128-bit pairing ID, TTL и single-use status;
- `artifact_kiosk_request_nonces`
  - durable anti-replay ledger подписанных device-запросов;
- `artifact_kiosk_admin_notifications`
  - deduplicated transactional outbox, создаваемый в одной транзакции с award.

Kiosk-award попадает в существующий сундук как канонический `Spin/Coupon`, но `Spin.source = "artifact_kiosk"`. Все обычные cooldown, stock, limit, recent-prize, boost-usage, stats и export запросы явно исключают этот source, поэтому kiosk-приз виден пользователю, не вмешиваясь в обычное Telegram-колесо.

### API v1

```text
POST /api/artifact-kiosk/session
GET  /api/artifact-kiosk/session/{session_id}
POST /api/artifact-kiosk/session/{session_id}/auth-mode
POST /api/artifact-kiosk/session/{session_id}/auth/start
GET  /api/artifact-kiosk/auth/callback
POST /api/artifact-kiosk/session/{session_id}/spin
POST /api/artifact-kiosk/session/{session_id}/finish
```

`POST .../spin` принимает только:

```json
{
  "request_id": "device-generated-uuid"
}
```

Ответ содержит неизменяемый server-selected prize, expiry, coupon code и два явных QR payload:

```json
{
  "issue_id": "...",
  "source_credit": "base",
  "prize": {
    "id": "DEP1K",
    "label": "ДЕПОЗИТ 1 000 ₽"
  },
  "coupon": {
    "code": "VNVNC-K-...",
    "redeem_qr_payload": "VNVNC-K-...",
    "regular_wheel_qr_payload": "https://t.me/vnvncbattlebot?start=wheel",
    "expires_at": "..."
  }
}
```

Повтор с тем же `(device_id, request_id)` всегда возвращает тот же issue/coupon и не печатает/уведомляет второй раз. ФОТОБУДКА ВИНОВНИЦЫ хранит unresolved `request_id` через timeout/обрыв ответа, блокирует смену flow, новую сессию и выход до разрешения границы и повторяет именно исходный запрос; новый UUID создаётся только после подтверждённо non-retryable отказа.

Машина использует отдельный per-device credential с timestamp, nonce и HMAC тела. Секрет provisioned через environment/systemd, сравнение constant-time, пустой/default ключ запрещён.

## 6. Staff scanner и безопасность погашения

Основной QR чека содержит только raw uppercase coupon code — это текущий scanner contract.

До включения денежных призов обязательны backend-фиксы:

- scanner отправляет `X-Telegram-Init-Data: tg.initData`;
- Vercel proxy сохраняет этот header;
- backend проверяет Telegram signature и свежесть `auth_date`;
- staff ID берётся только из подписанного initData;
- `/validate` не отдаёт PII без staff auth;
- redeem использует row lock/atomic conditional update;
- два конкурентных redeem дают ровно один success;
- expiry comparison использует `expires_at <= now`.

Никакие депозитные призы не выходят в production до прохождения этих security gates.

## 7. Машинная state machine

```text
ENTRY
  → AUTH_QR (default/persistent AUTH flow)
    ↔ READY_GUEST (6 = GUEST, 4 = AUTH; selection persists)
    → AUTH_POLL → BOOST_STATUS
  → AWARDING
  → SPINNING
  → REVEAL
  → RESULT
    → BONUS_READY (до 2 раз) → AWARDING → SPINNING → REVEAL
  → RECEIPT_READY
  → CLEAR_IDENTITY
  → NEXT_GUEST
```

Правила:

- барабан неподвижен, пока backend не зафиксировал prize;
- при network/backend error нет театрального спина, coupon или печати;
- UI показывает `СВЯЗИ НЕТ · ПРИЗ НЕ РАЗЫГРАН` и даёт повтор;
- prize выдаётся один раз, даже если печать не удалась;
- принтерная ошибка не делает re-spin;
- выход во время `AWARDING`/print откладывается до безопасной точки.
- identity очищается только после сохранения всех issues; logout не удаляет prize из сундука и не меняет redemption code;
- persistent flow хранит только `AUTH|GUEST`, но никогда не Telegram identity предыдущего гостя.

## 8. Ввод и hidden mode

До этой работы input layer не публиковал release нумпада. Реализация:

- добавить `PRIZE_DRUM_TOGGLE`;
- публиковать отдельные KP9 press/release edges и считать ровно 2,0 секунды через общий frame clock `HoldKeyDetector`;
- игнорировать key-repeat;
- emit ровно один toggle на 2,0 сек;
- rearm только на KEYUP;
- не пропускать обычный `KEYPAD_INPUT("9")`, иначе фотобудка воспримет его как спуск;
- повторить ту же семантику в simulator;
- проверить NumLock/scancode на ФОТОБУДКА ВИНОВНИЦЫ.

KP4/KP6 создают и arcade navigation event, и зеркальный digit event. Prize drum принимает оба источника для совместимости, но дедуплицирует физическую пару по flow/time, поэтому один нажим меняет выбор ровно один раз.

## 9. Визуальный язык и motion spec

Не плоское колесо, а огромный вертикальный барабан. Один сектор доминирует на 128×128; сверху и снизу видны только короткие соседние края.

### Геометрия

- drum viewport: `x=1..126`, `y=4..123`;
- победный билет: `116×68`, полностью виден и оптически зафиксирован по центру;
- соседние билеты: `106×64`, приглушены; в коротких peeks сверху/снизу обязательно читаются названия соседних призов;
- selector: крупный белый шеврон слева, направленный вправо в победный билет;
- геометрия VPISKA access ticket: side notches и крупный prize title; декоративные `VNVNC`, ID, barcode, mode и служебные подписи удалены;
- off-white grid chamber, red winner, muted paper neighbors, black/red keylines;
- каждый из восьми визуальных секторов имеет вручную заданную крупную раскладку на одну–две строки; generic auto-shrink не используется;
- на центральном секторе остаётся только название приза.

### Цвет

- основной VNVNC red;
- white/off-white;
- black/deep burgundy только для текста и механической глубины;
- без generic gradients, neon и лишних частиц.

### Emil motion

Цель — отчётливое ощущение настоящего slot machine: инерция тяжёлого барабана, механический pointer, синхронный звук, нарастающее ожидание и сильная фиксация выигрыша. По позднейшему прямому решению владельца используются два видимых false near-hit: барабан почти фиксируется на двух других секторах, затем снова резко подхватывается. Это presentation-only драматургия: prize уже атомарно выбран backend, клиент никогда его не меняет и всегда приходит ровно в серверный сектор.

Визуальная лента — не восемь карточек подряд и не сотни материализованных
секторов. Это один зацикленный барабан из 24 секторов: каждый из восьми
визуальных призов встречается ровно три раза, включая два невыигрышных
presentation-only депозита. Порядок заново перемешивается на каждую выдачу,
одинаковые сектора не соседствуют даже на круговом стыке. Seed строится из
неизменяемой серверной выдачи, поэтому retry показывает ту же ленту. Первые
восемь секторов идут медленно; затем движение ускоряется и продолжает ходить по
тому же кругу.

| Фаза | Движение |
|---|---|
| Нажатие | 0–120 ms, scale `0.97 → 1`, `cubic-bezier(.23,1,.32,1)` |
| Backend wait | барабан стоит; очень лёгкий checking shimmer |
| Старт | 300 ms механическая пауза, затем 8 случайных секторов по 450 ms каждый |
| Быстрый ход | ускорение по тому же 18-секторному кругу; ticks синхронны пересечениям секторов |
| Near-hit 1 | торможение почти в сектор, recoil, короткая ложная фиксация, резкий re-kick |
| Near-hit 2 | второй distinct сектор, более тяжёлая фиксация, повторный re-kick |
| Финальный хвост | overshoot на `0.14` сектора, backlash и точный settle |
| Reveal | winner flash, card enter 240–420 ms |
| В сундук | 560 ms directed “genie” motion только для paired user |

Slot-machine feedback работает как единая система:

- короткий соленоидный удар при старте;
- частые сухие clicks при пересечении sector boundaries;
- cadence замедляется примерно от 50 до 650 ms;
- pointer физически отгибается и возвращается на каждом секторе;
- четыре последних clicks намеренно читаются отдельно;
- финальная фиксация даёт red/white flash и rising five-note win arpeggio;
- количество доступных спинов влияет на backend-flow, но не добавляет служебные надписи на экраны;
- idle имеет очень медленный механический breathing/parallax, а не мёртвый экран.

Обычные переходы занимают 100–240 ms. Длинный motion разрешён только барабану и выигрышу. Рендер использует заранее подготовленные Pygame surfaces и position/transform updates; шрифты не растеризуются заново каждый кадр. Есть reduced-motion/debug режим для frame-by-frame и slow-motion QA.

## 10. Main, ticker и LCD

### Main 128×128

- ready/idle: только крупный барабан; никаких `ЖМИ`, `VNVNC`, boost/auth/key legends;
- auth: Telegram QR показан сразу без подписи; `6` по-прежнему переводит в persistent guest-flow, но клавиша нигде не подписана;
- guest: тот же чистый барабан; `4` возвращает persistent auth-flow, но клавиша нигде не подписана;
- QR: короткий server-issued pairing URL занимает почти весь экран; EC-Q v4 `123×123`, integer scale 3, quiet zone 12 px, Telegram icon ≤15% с белой подложкой; длинный provider URL fail-closed не кодируется на LED;
- spin/reveal: один гигантский prize-only sector и видимые соседние названия сверху/снизу;
- result: redemption QR и крупное название приза, без служебной подписи;
- regular electronic wheel QR остаётся только на чеке и в bot message.

### Ticker 48×8

Тикер не бывает мёртвым: в `CONNECTING/AUTH_QR` работает текст-free scan pulse; в `READY/ISSUING/SPINNING` он синхронно показывает название проходящего через центр сектора; в `REVEAL/RESULT` фиксирует выигранный приз. Никакие `TG`, boost или key legends не возвращаются. Используется проверенный full-height renderer без уменьшения штатного шрифта. Из-за электрической калибровки именно этого шкафа ticker является единственным исключением из red/white palette: цвет строго `(0,255,48)`, `safe_left=8`, поэтому используется только 40 физически читаемых колонок. Красный канал на этом устройстве деформирует буквы. Pixel-golden тесты требуют нулевые lit pixels до `x=8` и полное размещение названия в 40 читаемых колонках.

### LCD 16×1

LCD в `CONNECTING/AUTH_QR` показывает только bouncing scan marker без слов. В `READY/ISSUING/SPINNING` он синхронно повторяет проходящий prize headline, а в `REVEAL/RESULT` фиксирует выигранный приз. Никаких `TG`, boost, key legends или статусов печати.

## 11. Чек

Основной target — подключённый 80mm RP80/ESC-POS roll printer. Для режима создаётся отдельный `WheelPrizeRollReceiptGenerator`; generic receipt renderer не используется. Автоопределение требует sysfs VID:PID RP80 `0fe6:811e`; IP-802 `353d:1249` не может быть выбран как RP80. Ручной override допускается только через отдельный `ARTIFACT_RP80_PRINTER_PORT`, а не generic printer env.

Композиция сверху вниз:

1. канонический VNVNC Classic logo;
2. точное публичное имя `ФОТОБУДКА ВИНОВНИЦЫ`;
3. заголовок `ТВОЙ ПРИЗ`, крупное название и условия приза;
4. инструкция показать основной staff redemption QR сотруднику на стойке напротив гардероба;
5. coupon code текстом, точные issue/expiry, `1 ПРИЗ · 1 ПОГАШЕНИЕ`;
6. толстый разделитель;
7. блок обычного электронного колеса VNVNC;
8. второй QR на `https://t.me/vnvncbattlebot?start=wheel`.

QR-коды визуально и физически разделены:

- redemption QR — без встроенного логотипа для максимальной надёжности;
- regular-wheel QR — Telegram icon в центре, EC-H;
- подписи однозначно говорят, какой QR погашает приз;
- оба QR проходят decode из PNG preview и с реального термочека.

Канонический logo asset:

```text
/Users/kirniy/dev/modular-arcade/assets/logos/vnvnc-logo-classic-border-letters-black.png
SHA-256 6608303c03fb0565f3c998e8cda85064303477edbb672f07e55a9b462ac79570
```

Если printer отсутствует, production не может молча перейти в mock-success. Экран сохраняет redemption QR, показывает `ПЕЧАТЬ НЕ ГОТОВА`, отправляет admin alert; award остаётся действительным и не разыгрывается повторно.

## 12. Admin notifications

Только post-commit, с idempotency:

- prize issue: `ФОТОБУДКА ВИНОВНИЦЫ · БАРАБАН`, device, BASE/BOOST, prize, code, expiry, kiosk night/week remainder;
- pairing: пользователь, session, привязанные issues, boost state;
- print error/retry;
- redemption: сотрудник, prize, anonymous/paired, success/replay/expired.

Формулировка счётчика: `за эту неделю: N`. Вероятности и внутренние лимиты публично не показываются.

## 13. Файлы реализации

### `/Users/kirniy/dev/modular-arcade`

- `src/artifact/core/events.py` — dedicated toggle/release events;
- `src/artifact/hardware/runner.py` — KP9 long-hold, KP4/6 dedup;
- `src/artifact/simulator/window.py` — simulator parity;
- `src/artifact/modes/manager.py` — hidden exclusive mode lifecycle;
- `src/artifact/modes/prize_drum.py` — state machine/rendering;
- `src/artifact/services/vnvnc_kiosk.py` — signed async API client/idempotency;
- `src/artifact/printing/wheel_prize_roll.py` — VNVNC receipt;
- `src/artifact/printing/manager.py` — explicit prize receipt routing, no mock-success;
- `scripts/render_prize_drum_previews.py` — reproducible real-renderer PNG/OIDC/H.264 QA artifacts;
- `scripts/run_prize_drum_canary_backend.py` — loopback-only signed non-redeemable backend для реального RP80 soak;
- `assets/logos/...` and new purpose-built red/white prize icons;
- focused tests for input, state, render, ticker, QR, receipt and failure paths.

### `/Users/kirniy/dev/vnvnc-bot`

- DB migration for kiosk session/policy/issue/bonus/outbox tables;
- canonical inactive prize definitions;
- kiosk service and API v1;
- OIDC start/callback/JWKS validation;
- chest union for paired kiosk issues;
- boost lookup/recheck and kiosk-specific consumption;
- scanner signed initData, atomic redemption and exact expiry boundary fixes;
- post-commit notifications;
- отдельный durable paired-user outbox и strict Telegram sender с retry;
- dry-run-first policy configurator, который требует явный approved manifest и двойное подтверждение production apply;
- focused API, concurrency, auth, expiry and scanner tests.

Оба shared backend hardening-пункта реализованы локально: pending OIDC attempts инвалидируются при switch/finish, callback требует точную единственную активную попытку и pristine Telegram session; admin outbox считается доставленным только после хотя бы одного Telegram `message_id`, а пустая конфигурация, invalid token и полный send failure оставляют запись для retry. Admin payload содержит prize, code, source, точный expiry и обе даты `TIX1FREE`; paired-user payload реализован отдельно.

## 13.1. Проверяемая готовность на 26 августа 2026

| Контур | Состояние | Доказательство / следующий gate |
|---|---|---|
| Hidden KP9, 4/6, deferred exit | локально готов | input/lifecycle tests |
| Барабан, motion, звук, result | локально готов | real state-machine H.264 preview; user visual approval нужен |
| Telegram OIDC QR | локально готов | exact decode 45-char short URL, EC-Q v4, 123×123, 3 px/module; real LED scan нужен |
| Boost 0/1/2+ | локально готов | server recheck при spin; служебный boost copy на устройстве отсутствует; live channel check нужен |
| Server-selected award/idempotency | локально готов | timeout retry + 60-spin preflight |
| Сундук + личное сообщение | локально готов | durable user outbox, 8 focused delivery tests; live bot DM нужен |
| Admin notification | локально готов | strict durable sender, retry/all-fail/partial/concurrency tests; live bot delivery нужен |
| Scanner/expiry/pass | локально готов | concurrency и 06:59:59/07:00 tests; physical staff scan нужен |
| RP80 receipt | локально готов | PNG QRs decode; реальная бумага/unplug/retry нужны |
| Policy values | не утверждены | operator approval sheet, seed не выполнялся |
| Production | выключен | только после canary и 50+ physical soak |

## 14. Реализация по этапам

### Phase A — backend foundation

Schema, policies, idempotent server-selected spin, expiry, scanner hardening, tests. No UI spin is enabled until this passes.

### Phase B — Telegram/OIDC/boost

BotFather Allowed URLs, OIDC callback, session pairing, chest union, phone confirmation page, `getUserChatBoosts`, capped +2 policy and concurrency tests.

### Phase C — ФОТОБУДКА ВИНОВНИЦЫ vertical slice

Hidden KP9 mode, signed API client, deterministic drum, main/ticker/LCD states, audio ticks. Feature flag remains off in production.

### Phase D — receipt

Classic logo, two QR blocks, expiry copy, exact raw code, RP80 routing, PNG golden preview, print/decode tests.

### Phase E — user trial

Deliver a local simulator build first. Controls: hold `9`, `4/6`, main button. It uses a stub server and mock printer so the visual/motion pass can be approved without real prizes.

Then enable staging integration with test-only coupons and admin notifications, followed by one supervised ФОТОБУДКА ВИНОВНИЦЫ canary.

### Phase F — production

- provision secrets outside git;
- seed explicit kiosk weights/limits;
- verify bot admin access to channel boost data;
- exercise all prizes through staff scanner;
- print and scan both receipt QR codes;
- run 50+ spin/print soak, backend outage and printer-unplug scenarios;
- enable `ARTIFACT_PRIZE_DRUM_ENABLED=1` only after gates pass;
- deploy with rollback to ordinary photobooth profile.

## 15. Acceptance gates

- KP9 1.99s: no toggle; 2.0s: exactly one; repeat ignored; release rearms.
- Holding KP9 never triggers a photo capture.
- Hidden mode never appears in the normal selector.
- KP4/KP6 navigate exactly once.
- Default flow is AUTH; `6` persistently selects GUEST; `4` persistently selects AUTH.
- After all allowed spins complete, paired identity and login token are cleared before the next guest, while the chosen AUTH/GUEST flow remains.
- Backend chooses every prize; client cannot override it.
- Same request ID returns same issue and exactly one print/notification.
- Lost response after backend commit is recovered with the same request ID and returns the already-issued award.
- No backend confirmation means no drum animation or award.
- Kiosk and ordinary wheel limits never affect each other.
- Guest/auth-no-boost/one-boost/two-plus-boost paths yield exactly 1/1/2/3 total spins.
- At most two bonus spins per Telegram user per club night under concurrent requests; each active boost unlocks one slot up to the cap.
- Non-pass expiry works at `06:59:59`/`07:00:00`.
- `TIX1FREE` has explicit dates, one person, one total redemption.
- Paired prizes appear in the existing chest without consuming normal wheel cooldown.
- Staff scanner requires signed fresh initData and allows only one concurrent redemption.
- Drum lands on the exact server prize for varied frame times.
- Slot-machine ticks, pointer deflection, two false-lock/re-kick beats, final overshoot/settle and win audio remain frame-synchronized under load.
- Ticker and LCD are active before a win without service copy: scan graphics during pairing and centered prize names during READY/ISSUING/SPINNING; ticker content fits the calibrated 40-column readable area (`safe_left=8`) without left clipping or red-channel distortion.
- Both QR codes decode from final PNG and real thermal paper.
- Printer unplug is visible and never becomes mock success/re-spin.
- Main display, ticker, LCD, printer, bot message and admin notification agree on the prize; all public device references say exactly `ФОТОБУДКА ВИНОВНИЦЫ`.

## 16. Before / after

| Сейчас | После реализации |
|---|---|
| Обычная фотобудка | Скрытый staff-controlled prize drum через hold KP9 |
| Нет физического server-authoritative spin flow | Idempotent VNVNC kiosk API и независимые limits |
| Telegram не связан с физической выдачей | Официальный OIDC Login → тот же VNVNC user/chest |
| Нет причины логиниться | Active channel boosts → до +2 kiosk spins |
| Generic/photobooth print path | VNVNC Classic receipt с двумя чётко разделёнными QR |
| Риск client-selected prize/duplicate redeem | Server choice, signed device, atomic single-use scanner |
| Обычный selector/input | Эксклюзивный режим с 4/6 и безопасным deferred exit |
