# TravelHub

Микросервисная система бронирования туров: три независимых REST-сервиса на FastAPI, общая база PostgreSQL, reverse proxy nginx с Web UI, и запуск одной командой через Docker Compose.

Проект разработан в рамках финальной работы по дисциплине «Введение в DevSecOps» и входит в моё портфолио.

![Python](https://img.shields.io/badge/Python-3.9-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![nginx](https://img.shields.io/badge/nginx-1.27-009639?logo=nginx&logoColor=white)

## Содержание

- [Архитектура](#архитектура)
- [Технологии](#технологии)
- [Структура репозитория](#структура-репозитория)
- [Быстрый старт](#быстрый-старт)
- [Web UI](#web-ui)
- [API](#api)
- [Как работает бронирование](#как-работает-бронирование)
- [Сценарий проверки (curl)](#сценарий-проверки-curl)
- [C4 архитектурные диаграммы](#c4-архитектурные-диаграммы)
- [Остановка и очистка](#остановка-и-очистка)

## Архитектура

```
                ┌──────────────────┐
   браузер ───► │      nginx       │ :80
                │  (reverse proxy  │
                │   + web UI)      │
                └─┬──────┬──────┬──┘
                  │      │      │
            /api/users /api/tours /api/bookings
                  ▼      ▼      ▼
            ┌────────┐ ┌────────┐ ┌──────────────┐
            │ User   │ │ Tour   │ │ Booking      │
            │Service │ │Service │ │ Service      │
            │ :8000  │ │ :8001  │ │ :8002        │
            └───┬────┘ └───┬────┘ └──────┬───────┘
                │          │             │
                │          │   ◀── HTTP ─┘ (проверка user/tour)
                │          │             │
                └────┬─────┘             │
                     ▼                   │
              ┌──────────────┐           │
              │ PostgreSQL   │ ◀─────────┘
              │   :5432      │
              │ (volume      │
              │  db_data)    │
              └──────────────┘
```

| Компонент | Порт | Назначение |
| --------- | ---- | ---------- |
| **nginx** | 80 | Reverse proxy + раздача статики фронтенда |
| **User Service** | 8000 | Управление данными пользователей |
| **Tour Service** | 8001 | Каталог доступных туров |
| **Booking Service** | 8002 | Оформление бронирований + inter-service calls |
| **PostgreSQL** | 5432 | Единая реляционная БД для всех сущностей |

Подробная архитектура в [docs/architecture_c4.md](docs/architecture_c4.md) — 3 уровня C4: Context, Container, Component.

## Технологии

- **Язык:** Python 3.9
- **Фреймворк:** FastAPI + Uvicorn
- **БД:** PostgreSQL 16 (драйвер `psycopg2-binary`)
- **Reverse proxy:** nginx 1.27
- **Frontend:** HTML/CSS/ванильный JS (без сборки)
- **Контейнеризация:** Docker, Docker Compose
- **CI:** GitHub Actions (`.github/workflows`)

## Структура репозитория

```
TravelHub/
├── .github/workflows/       # CI-пайплайны
├── booking-service/         # сервис бронирований
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── tour-service/            # сервис туров
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── user-service/            # сервис пользователей
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── frontend/                # статический Web UI
│   ├── index.html
│   ├── style.css
│   └── app.js
├── nginx/
│   └── nginx.conf           # reverse proxy + static
├── docs/
│   ├── architecture.png     # экспорт схемы для защиты
│   ├── architecture_c4.md   # C4 диаграммы (Mermaid)
│   └── curl_examples.sh     # готовый сценарий проверки
├── .gitignore
├── docker-compose.yml
└── README.md
```

## Быстрый старт

**Требования:** установленные Docker и Docker Compose.

1. Клонируйте репозиторий и перейдите в него:

   ```bash
   git clone https://github.com/egortonkikh/TravelHub.git
   cd TravelHub
   ```

2. Соберите и запустите все сервисы:

   ```bash
   docker compose up --build -d
   ```

3. Проверьте, что 5 контейнеров Up:

   ```bash
   docker compose ps
   ```

   Должно быть: `db`, `user-service`, `tour-service`, `booking-service`, `nginx` — все Up.

4. Откройте Web UI:

   ```
   http://localhost
   ```

   Либо Swagger-документацию каждого сервиса напрямую:

   | Сервис | URL |
   | ------ | --- |
   | User Service | http://localhost:8000/docs |
   | Tour Service | http://localhost:8001/docs |
   | Booking Service | http://localhost:8002/docs |

## Web UI

Современный одностраничный интерфейс (`http://localhost`) с тремя секциями:

- **Пользователи** — форма создания + список всех пользователей
- **Туры** — форма создания + список всех туров
- **Бронирования** — форма с dropdown-ами (заполняется из существующих users/tours) + список всех бронирований

Каждая секция имеет кнопку обновления (↻). Создание сущности через форму автоматически обновляет все списки. Уведомления об успехе/ошибке показываются в нижней части экрана.

## API

| Сервис | Метод | Путь | Описание |
| ------ | ----- | ---- | -------- |
| User | `POST` | `/users` | Создать пользователя |
| User | `GET` | `/users` | Список всех пользователей |
| User | `GET` | `/users/{user_id}` | Получить пользователя по ID |
| Tour | `POST` | `/tours` | Добавить тур |
| Tour | `GET` | `/tours` | Список всех туров |
| Tour | `GET` | `/tours/{tour_id}` | Получить тур по ID |
| Booking | `POST` | `/bookings` | Оформить бронирование |
| Booking | `GET` | `/bookings` | Список всех бронирований |
| Booking | `GET` | `/bookings/{id}` | Получить бронирование по ID |

Через nginx (с порта 80) те же endpoint'ы доступны с префиксом `/api/`:
`/api/users`, `/api/tours`, `/api/bookings`.

Схемы запросов и ответов смотрите в Swagger (`/docs`) каждого сервиса.

## Как работает бронирование

1. Клиент отправляет `POST /api/bookings` в Booking Service (через nginx).
2. Booking Service делает HTTP-запрос `GET /users/{user_id}` в User Service и проверяет, что пользователь существует.
3. Затем делает HTTP-запрос `GET /tours/{tour_id}` в Tour Service и проверяет, что тур существует.
4. Если обе проверки пройдены — бронирование сохраняется в PostgreSQL.
5. Если user или tour не найден — возвращается `404`.
6. Если user-service или tour-service недоступны — возвращается `503`.

Так сервисы остаются независимыми: Booking Service не лезет в чужие таблицы напрямую, а общается с соседями только по их API.

## Сценарий проверки (curl)

В репозитории есть готовый скрипт с полным сценарием проверки — [`docs/curl_examples.sh`](docs/curl_examples.sh).

Запуск:

```bash
chmod +x docs/curl_examples.sh
./docs/curl_examples.sh
```

Скрипт последовательно:

1. Создаёт пользователя Егор
2. Создаёт тур «Москва — Питер»
3. Создаёт бронирование (с реальными ID)
4. Получает список пользователей
5. Получает список туров
6. Получает список бронирований
7. Получает конкретное бронирование по ID
8. Проверяет inter-service взаимодействие (бронирование с несуществующим user → 404)
9. Описывает шаги для ручной проверки персистентности

## C4 архитектурные диаграммы

В файле [`docs/architecture_c4.md`](docs/architecture_c4.md) — три уровня C4:

- **Context** — система в окружении (клиент → TravelHub → PostgreSQL)
- **Container** — высокоуровневые компоненты (nginx, 3 сервиса, БД)
- **Component** — внутреннее устройство booking-service (endpoints, helpers, schema)

Диаграммы используют **Mermaid** — GitHub рендерит их автоматически в README.

## Остановка и очистка

```bash
docker compose down        # остановить контейнеры (данные остаются)
docker compose down -v     # остановить и удалить данные БД (volume db_data)
```

## Проверка персистентности данных

Чтобы убедиться, что данные сохраняются между перезапусками:

```bash
# 1. Создать данные
curl -X POST http://localhost/api/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","email":"test@example.com"}'

# 2. Остановить без удаления volume
docker compose down

# 3. Поднять снова
docker compose up -d

# 4. Данные на месте
curl http://localhost/api/users
```

## Автор

Егор Тонких — [@egortonkikh](https://github.com/egortonkikh)
