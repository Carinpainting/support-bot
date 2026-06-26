# Support Bot

Telegram-бот техподдержки онлайн-сервиса ретуширования автомобилей. Принимает обращения от пользователей в чате и автоматически создаёт карточки в Trello с приоритетом, описанием и приложенным скриншотом.

## Возможности

- 📝 Создание обращения через пошаговый сценарий (заголовок → описание → скриншот → приоритет)
- 📎 Прикрепление фото в виде вложения к карточке Trello
- 🎨 Цветные метки в Trello по приоритету (🟢 низкий / 🟡 средний / 🔴 высокий)
- 📋 Просмотр своих активных обращений (фильтрация по `TELEGRAM_USER_ID` в описании карточки)
- 🌐 Опциональная работа через SOCKS/HTTP-прокси (`PROXY_URL`)

## Стек

- Python 3.11+
- [aiogram 3.4](https://docs.aiogram.dev/) — Telegram Bot API
- [aiohttp 3.9](https://docs.aiohttp.org/) — HTTP-клиент к Trello API
- [aiohttp-socks](https://pypi.org/project/aiohttp-socks/) — поддержка прокси
- [python-dotenv](https://pypi.org/project/python-dotenv/) — переменные окружения
- [Poetry](https://python-poetry.org/) — управление зависимостями

## Установка

```bash
git clone <repo-url>
cd support-bot
poetry install
```

## Конфигурация

Создайте файл `.env` в корне проекта:

```env
BOT_TOKEN=123456:ABC-DEF...           # токен от @BotFather
TRELLO_API_KEY=...                    # https://trello.com/app-key
TRELLO_TOKEN=...                      # OAuth-токен Trello

TRELLO_LIST_LOW=<list_id>             # ID списка для низкого приоритета
TRELLO_LIST_MEDIUM=<list_id>          # ID списка для среднего приоритета
TRELLO_LIST_HIGH=<list_id>            # ID списка для высокого приоритета

PROXY_URL=socks5://user:pass@host:port  # опционально
```

### Где взять идентификаторы списков Trello

ID списка можно получить через API: `https://api.trello.com/1/boards/<boardId>/lists?key=<KEY>&token=<TOKEN>`.

## Запуск

```bash
poetry run python main.py
```

Бот работает в режиме long polling.

## Структура проекта

```
.
├── main.py                # точка входа, обработчики бота, интеграция с Trello
├── pyproject.toml         # зависимости Poetry
├── poetry.lock
└── .github/workflows/
    └── deploy.yml         # CI: lint → test → deploy по SSH на master
```

### Основные компоненты `main.py`

- `TaskForm` — FSM-состояния пошагового создания задачи
- `create_trello_card()` — создаёт карточку, ставит цветную метку, опционально прикрепляет фото
- `get_user_cards()` — собирает карточки пользователя по всем трём спискам, фильтрует по маркеру `TELEGRAM_USER_ID:<id>` в описании
- Обработчики `cmd_start`, `new_task`, `list_my_tasks`, `help_cmd`

## Деплой

CI-пайплайн в `.github/workflows/deploy.yml`:

1. **lint** — `flake8 main.py` (мягкий режим, `--exit-zero`)
2. **test** — проверка компиляции и импортов
3. **deploy** — SSH-подключение к серверу, `git pull` + `poetry install` + `systemctl restart support-bot`

Деплой срабатывает только при push в `master`. Требуемые GitHub Secrets:
`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PORT`.

На сервере ожидается:
- проект в `/home/orangepi/support-bot`
- виртуальное окружение `.venv`
- systemd-юнит `support-bot.service`

## Лицензия

Учебный проект.
