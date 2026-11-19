# TravelHub

Микросервисная система бронирования туров с расширенной архитектурой: три независимых REST-сервиса на FastAPI, общая база PostgreSQL, кэш Redis, брокер сообщений RabbitMQ, reverse proxy nginx с Web UI, и запуск одной командой через Docker Compose.

Проект разработан в рамках финальной работы по дисциплине «Введение в DevSecOps» и входит в моё портфолио.

![Python](https://img.shields.io/badge/Python-3.9-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3.13-FF6600?logo=rabbitmq&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![nginx](https://img.shields.io/badge/nginx-1.27-009639?logo=nginx&logoColor=white)

## Содержание

- [Архитектура](#архитектура)
- [Технологии](#технологии)
- [Структура репозитория](#структура-репозитория)
- [Быстрый старт](#быстрый-старт)
- [Web UI](#web-ui)
- [API](#api)
- [Кэширование (Redis)](#кэширование-redis)
- [Брокер сообщений (RabbitMQ)](#брокер-сообщений-rabbitmq)
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
        ┌───────┴──┐  ┌────┴─────┐       │ publish booking.created
        │  Redis   │  │  Redis   │       ▼
        │  cache   │  │  cache   │  ┌─────────┐
        └─────┬────┘  └─────┬────┘  │RabbitMQ │
              │             │       │ broker  │
              │             │       └────┬────┘
              ▼             ▼            │ consume
        ┌──────────────────────┐         │
        │    PostgreSQL  :5432 │ ◀───────┼──────────┐
        │    (volume db_data)  │         │          │
        └──────────────────────┘         │          │
                                         ▼          │
                              ┌──────────────────────┐
                              │ Notification Worker  │
                              │ (consumer, async)    │
                              └──────────────────────┘
```

| Компонент | Порт | Назначение |
| --------- | ---- | ---------- |
| **nginx** | 80 | Reverse proxy + раздача статики фронтенда |
| **User Service** | 8000 | Управление пользователями + кэш Redis |
| **Tour Service** | 8001 | Каталог туров + кэш Redis |
| **Booking Service** | 8002 | Бронирования + inter-service HTTP + публикация событий |
| **PostgreSQL** | 5432 | Единая реляционная БД |
| **Redis** | 6379 | Кэш для user-service и tour-service |
| **RabbitMQ** | 5672 / 15672 | Брокер сообщений (AMQP + management UI) |
| **Notification Worker** | — | Consumer: обрабатывает события `booking.created` |

## Технологии

- **Язык:** Python 3.9
- **Фреймворк:** FastAPI + Uvicorn
- **БД:** PostgreSQL 16 (драйвер `psycopg2-binary`)
- **Кэш:** Redis 7 (cache-aside pattern)
- **Брокер сообщений:** RabbitMQ 3.13 (AMQP protocol)
- **Reverse proxy:** nginx 1.27
- **Frontend:** HTML/CSS/ванильный JS (без сборки)
- **Контейнеризация:** Docker, Docker Compose
- **CI:** GitHub Actions (`.github/workflows`)

## Структура репозитория

```
TravelHub/
├── .github/workflows/         # CI-пайплайны
├── booking-service/           # сервис бронирований
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── tour-service/              # сервис туров
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── user-service/              # сервис пользователей
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── notification-worker/       # consumer событий booking.created
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── frontend/                  # статический Web UI
│   ├── index.html
│   ├── style.css
│   └── app.js
├── nginx/
│   └── nginx.conf             # reverse proxy + static
├── docs/
│   ├── architecture.png       # экспорт схемы для защиты
│   ├── architecture_c4.md     # C4 диаграммы (Mermaid)
│   └── curl_examples.sh       # готовый сценарий проверки
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

3. Проверьте, что 8 контейнеров Up:

   ```bash
   docker compose ps
   ```

   Должно быть: `db`, `redis`, `rabbitmq`, `user-service`, `tour-service`, `booking-service`, `notification-worker`, `nginx`.

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

5. Откройте RabbitMQ Management UI:

   ```
   http://localhost:15672
   ```

   Login: `admin` / Password: `admin` — можно смотреть очереди, exchange, сообщения.

## Web UI

Современный одностраничный интерфейс (`http://localhost`) с тремя секциями:

- **Пользователи** — форма создания + список всех пользователей
- **Туры** — форма создания + список всех туров
- **Бронирования** — форма с dropdown-ами + список всех бронирований

## API

| Сервис | Метод | Путь | Описание |
| ------ | ----- | ---- | -------- |
| User | `POST` | `/users` | Создать пользователя |
| User | `GET` | `/users` | Список всех пользователей (с кэшем Redis) |
| User | `GET` | `/users/{user_id}` | Получить пользователя по ID (с кэшем Redis) |
| Tour | `POST` | `/tours` | Добавить тур |
| Tour | `GET` | `/tours` | Список всех туров (с кэшем Redis) |
| Tour | `GET` | `/tours/{tour_id}` | Получить тур по ID (с кэшем Redis) |
| Booking | `POST` | `/bookings` | Оформить бронирование + опубликовать событие |
| Booking | `GET` | `/bookings` | Список всех бронирований |
| Booking | `GET` | `/bookings/{id}` | Получить бронирование по ID |

Через nginx (с порта 80) те же endpoint'ы доступны с префиксом `/api/`:
`/api/users`, `/api/tours`, `/api/bookings`.

## Кэширование (Redis)

В user-service и tour-service реализован **cache-aside pattern** с возможностью управления стратегией через query-параметр `cache`.

### Режимы работы кэша

Тот же endpoint, но с параметром `?cache=...` контролируем поведение:

| URL | Режим | Что происходит |
|---|---|---|
| `GET /users/1` | **default** | Cache-aside: проверяем Redis, hit → отдали, miss → пошли в БД, записали в кэш |
| `GET /users/1?cache=refresh` | **refresh** | Пропускаем чтение кэша, идём в БД, обновляем кэш свежими данными |
| `GET /users/1?cache=bypass` | **bypass** | Ни читаем, ни пишем Redis — чистый запрос в БД |

**Когда что использовать:**
- `default` (или без параметра) — для 99% запросов, обычный cache-aside
- `refresh` — клиент подозревает устаревшие данные, хочет принудительно перечитать из БД и обновить кэш
- `bypass` — для дебага: точно узнать, что в БД прямо сейчас, минуя кэш

### Стандартное поведение (default)

1. При `GET /users/{id}` — сначала проверяется ключ `user:{id}` в Redis
2. Если есть — данные возвращаются из кэша (без запроса к БД)
3. Если нет (cache miss) — селектим из PostgreSQL, записываем в Redis с TTL 60 сек
4. При `POST /users` — кэш инвалидируется (ключи `user:*` и `users:all` удаляются)

То же для tours с ключами `tour:{id}` и `tours:all`.

**Fallback:** если Redis недоступен — сервисы работают напрямую с БД (`except redis.RedisError: pass`).

### Примеры curl

```bash
# Обычный cache-aside
curl http://localhost/api/users/1

# Принудительное обновление кэша (минуя чтение Redis, идём в БД, обновляем кэш)
curl http://localhost/api/users/1?cache=refresh

# Обход кэша (чистый запрос в БД, не трогаем Redis)
curl http://localhost/api/users/1?cache=bypass
```

## Брокер сообщений (RabbitMQ)

После создания бронирования booking-service публикует событие `booking.created` в exchange `bookings` (routing key `booking.created`, delivery_mode=2 — persistent).

**notification-worker** подписан на очередь `notification-worker`, consumes события и логирует их. В реальном продакшене здесь была бы:
- отправка email пользователю
- обновление analytics
- уведомление менеджера
- интеграция с платёжной системой

**Архитектурный плюс:** бронирование сохраняется в БД синхронно, но всё, что не нужно клиенту сразу (email, аналитика) — асинхронно через брокер. booking-service не блокируется на этих задачах.

**Management UI:** http://localhost:15672 (admin/admin) — можно видеть:
- exchange `bookings`
- queue `notification-worker`
- messages flowing through

## Как работает бронирование

1. Клиент отправляет `POST /api/bookings` в Booking Service (через nginx).
2. Booking Service делает HTTP-запрос `GET /users/{user_id}` в User Service (тот берёт из кэша Redis, если есть) и проверяет, что пользователь существует.
3. Затем делает HTTP-запрос `GET /tours/{tour_id}` в Tour Service (тоже через кэш Redis) и проверяет, что тур существует.
4. Если обе проверки пройдены — бронирование сохраняется в PostgreSQL.
5. Booking Service публикует событие `booking.created` в RabbitMQ.
6. notification-worker асинхронно обрабатывает событие (логирует, в проде — отправил бы email).
7. Клиенту возвращается ответ с `id` бронирования.

Синхронная часть (проверки + сохранение в БД) — обязательна для валидации.
Асинхронная часть (publish event + worker processing) — для side-effects.

## Сценарий проверки (curl)

В репозитории есть готовый скрипт с полным сценарием проверки — [`docs/curl_examples.sh`](docs/curl_examples.sh).

Запуск:

```bash
chmod +x docs/curl_examples.sh
./docs/curl_examples.sh
```

## C4 архитектурные диаграммы

В файле [`docs/architecture_c4.md`](docs/architecture_c4.md) — три уровня C4:
- **Context** — система в окружении (клиент → TravelHub → PostgreSQL)
- **Container** — высокоуровневые компоненты (nginx, 3 сервиса, Redis, RabbitMQ, worker, БД)
- **Component** — внутреннее устройство booking-service (endpoints, helpers, publisher)

## Остановка и очистка

```bash
docker compose down        # остановить контейнеры (данные остаются)
docker compose down -v     # остановить и удалить данные БД (volume db_data)
```

## Автор

Егор Тонких — [@egortonkikh](https://github.com/egortonkikh)
