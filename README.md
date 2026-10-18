# TravelHub

Микросервисная система бронирования туров: три независимых REST-сервиса на FastAPI, общая база PostgreSQL и запуск одной командой через Docker Compose.

Проект разработан в рамках финальной работы по дисциплине «Введение в DevSecOps» и входит в моё портфолио.

![Python](https://img.shields.io/badge/Python-3.9-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

## Содержание

- [Архитектура](#архитектура)
- [Технологии](#технологии)
- [Структура репозитория](#структура-репозитория)
- [Быстрый старт](#быстрый-старт)
- [API](#api)
- [Как работает бронирование](#как-работает-бронирование)
- [Остановка и очистка](#остановка-и-очистка)

## Архитектура

```
                 ┌──────────────────┐
   клиент ─────► │ Booking Service  │ :8002
                 └───┬──────────┬───┘
        HTTP: есть   │          │  HTTP: есть
        ли user?     ▼          ▼  ли тур?
            ┌──────────────┐ ┌──────────────┐
            │ User Service │ │ Tour Service │
            │    :8000     │ │    :8001     │
            └──────┬───────┘ └──────┬───────┘
                   │                │
                   └───────┬────────┘
                           ▼
                   ┌──────────────┐
                   │ PostgreSQL   │ :5432
                   └──────────────┘
```

| Компонент | Порт | Назначение |
| --------- | ---- | ---------- |
| **User Service** | 8000 | Управление данными пользователей |
| **Tour Service** | 8001 | Каталог доступных туров |
| **Booking Service** | 8002 | Оформление бронирований |
| **PostgreSQL** | 5432 | Единая реляционная БД для всех сущностей |

## Технологии

- **Язык:** Python 3.9
- **Фреймворк:** FastAPI + Uvicorn
- **БД:** PostgreSQL 16 (драйвер `psycopg2-binary`)
- **Контейнеризация:** Docker, Docker Compose
- **CI:** GitHub Actions (`.github/workflows`)

## Структура репозитория

```
TravelHub/
├── .github/workflows/   # CI-пайплайны
├── booking-service/     # сервис бронирований
├── tour-service/        # сервис туров
├── user-service/        # сервис пользователей
├── docs/                # документация проекта
└── docker-compose.yml   # запуск всей системы
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
   docker compose up --build
   ```

3. Откройте Swagger-документацию сервисов:

   | Сервис | URL |
   | ------ | --- |
   | User Service | http://localhost:8000/docs |
   | Tour Service | http://localhost:8001/docs |
   | Booking Service | http://localhost:8002/docs |

## API

| Сервис | Метод | Путь | Описание |
| ------ | ----- | ---- | -------- |
| User | `POST` | `/users` | Создать пользователя |
| User | `GET` | `/users/{user_id}` | Получить пользователя по ID |
| Tour | `POST` | `/tours` | Добавить тур |
| Tour | `GET` | `/tours/{tour_id}` | Получить тур по ID |
| Booking | `POST` | `/bookings` | Оформить бронирование |
| Booking | `GET` | `/bookings/{id}` | Получить бронирование по ID |

Схемы запросов и ответов смотрите в Swagger (`/docs`) каждого сервиса.

## Как работает бронирование

1. Клиент отправляет `POST /bookings` в Booking Service.
2. Booking Service делает HTTP-запрос в User Service и проверяет, что пользователь существует.
3. Затем делает HTTP-запрос в Tour Service и проверяет, что тур существует.
4. Если обе проверки пройдены, бронирование сохраняется в PostgreSQL.

Так сервисы остаются независимыми: Booking Service не лезет в чужие таблицы напрямую, а общается с соседями только по их API.

## Остановка и очистка

```bash
docker compose down        # остановить контейнеры
docker compose down -v     # остановить и удалить данные БД
```

## Автор

Егор Тонких — [@egortonkikh](https://github.com/egortonkikh)