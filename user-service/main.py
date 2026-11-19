import json
import os
from contextlib import asynccontextmanager
from enum import Enum

import psycopg2
import redis
from fastapi import FastAPI, HTTPException, Query
from psycopg2 import errors
from pydantic import BaseModel

DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
DB_NAME = os.getenv("DB_NAME", "app")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))

_redis = None


class CacheMode(str, Enum):
    """Стратегия работы с кэшем для GET-endpoint'ов."""
    default = "default"   # cache-aside: проверяем кэш, при промахе — БД + обновление кэша
    refresh = "refresh"   # пропустить чтение кэша, идти в БД, обновить кэш
    bypass = "bypass"     # пропустить и чтение, и запись кэша — чистый запрос в БД


def get_cache():
    """Возвращает Redis-клиент или None, если REDIS_URL не задан."""
    global _redis
    if not REDIS_URL:
        return None
    if _redis is None:
        _redis = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1)
    return _redis


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL
                )
                """
            )
        conn.commit()
    finally:
        conn.close()
    print("users table ready")
    yield


app = FastAPI(title="User Service", lifespan=lifespan)


class UserCreate(BaseModel):
    name: str
    email: str


def invalidate_user_cache(cache, user_id=None):
    """Сбрасывает кэш пользователей."""
    if not cache:
        return
    try:
        cache.delete("users:all")
        if user_id is not None:
            cache.delete(f"user:{user_id}")
    except redis.RedisError:
        pass  # кэш — не критичен, fallback к БД


@app.post("/users")
def create_user(user: UserCreate):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (name, email) VALUES (%s, %s) RETURNING id",
                (user.name, user.email),
            )
            new_id = cursor.fetchone()[0]
        conn.commit()
    except errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
    finally:
        conn.close()

    # Инвалидируем кэш — данные изменились
    cache = get_cache()
    invalidate_user_cache(cache)

    return {"id": new_id, "message": "User created successfully!"}


@app.get("/users")
def list_users(
    cache: CacheMode = Query(
        CacheMode.default,
        description="Стратегия кэша: default (cache-aside), refresh (force DB read + update cache), bypass (no cache)",
    ),
):
    cache_client = get_cache()
    cache_key = "users:all"

    # 1. default mode — пробуем кэш
    if cache_client and cache == CacheMode.default:
        try:
            cached = cache_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except redis.RedisError:
            pass  # fallback к БД

    # 2. Идём в БД (для refresh и bypass — всегда, для default — при cache miss)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, email FROM users ORDER BY id")
            rows = cursor.fetchall()
    finally:
        conn.close()

    data = [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]

    # 3. Записываем в кэш (default и refresh — да, bypass — нет)
    if cache_client and cache != CacheMode.bypass:
        try:
            cache_client.setex(cache_key, CACHE_TTL, json.dumps(data))
        except redis.RedisError:
            pass

    return data


@app.get("/users/{user_id}")
def get_user(
    user_id: int,
    cache: CacheMode = Query(
        CacheMode.default,
        description="Стратегия кэша: default (cache-aside), refresh (force DB read + update cache), bypass (no cache)",
    ),
):
    cache_client = get_cache()
    cache_key = f"user:{user_id}"

    # 1. default mode — пробуем кэш
    if cache_client and cache == CacheMode.default:
        try:
            cached = cache_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except redis.RedisError:
            pass  # fallback к БД

    # 2. Идём в БД
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, email FROM users WHERE id = %s",
                (user_id,),
            )
            result = cursor.fetchone()
    finally:
        conn.close()

    if result is None:
        raise HTTPException(status_code=404, detail="User not found")

    data = {"id": result[0], "name": result[1], "email": result[2]}

    # 3. Записываем в кэш (default и refresh — да, bypass — нет)
    if cache_client and cache != CacheMode.bypass:
        try:
            cache_client.setex(cache_key, CACHE_TTL, json.dumps(data))
        except redis.RedisError:
            pass

    return data
