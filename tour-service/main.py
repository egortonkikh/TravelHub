import json
import os
from contextlib import asynccontextmanager
from enum import Enum

import psycopg2
import redis
from fastapi import FastAPI, HTTPException, Query
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
                CREATE TABLE IF NOT EXISTS tours (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    price NUMERIC(10, 2) NOT NULL,
                    duration INT
                )
                """
            )
        conn.commit()
    finally:
        conn.close()
    print("tours table ready")
    yield


app = FastAPI(title="Tour Service", lifespan=lifespan)


class TourCreate(BaseModel):
    title: str
    description: str
    price: float
    duration: int


def invalidate_tour_cache(cache, tour_id=None):
    if not cache:
        return
    try:
        cache.delete("tours:all")
        if tour_id is not None:
            cache.delete(f"tour:{tour_id}")
    except redis.RedisError:
        pass


@app.post("/tours")
def create_tour(tour: TourCreate):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tours (title, description, price, duration) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (tour.title, tour.description, tour.price, tour.duration),
            )
            new_id = cursor.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    cache = get_cache()
    invalidate_tour_cache(cache)

    return {"id": new_id, "message": "Tour created successfully!"}


@app.get("/tours")
def list_tours(
    cache: CacheMode = Query(
        CacheMode.default,
        description="Стратегия кэша: default (cache-aside), refresh (force DB read + update cache), bypass (no cache)",
    ),
):
    cache_client = get_cache()
    cache_key = "tours:all"

    # 1. default mode — пробуем кэш
    if cache_client and cache == CacheMode.default:
        try:
            cached = cache_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except redis.RedisError:
            pass

    # 2. Идём в БД
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, title, description, price, duration FROM tours ORDER BY id"
            )
            rows = cursor.fetchall()
    finally:
        conn.close()

    data = [
        {
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "price": float(r[3]),
            "duration": r[4],
        }
        for r in rows
    ]

    # 3. Записываем в кэш (default и refresh — да, bypass — нет)
    if cache_client and cache != CacheMode.bypass:
        try:
            cache_client.setex(cache_key, CACHE_TTL, json.dumps(data))
        except redis.RedisError:
            pass

    return data


@app.get("/tours/{tour_id}")
def get_tour(
    tour_id: int,
    cache: CacheMode = Query(
        CacheMode.default,
        description="Стратегия кэша: default (cache-aside), refresh (force DB read + update cache), bypass (no cache)",
    ),
):
    cache_client = get_cache()
    cache_key = f"tour:{tour_id}"

    # 1. default mode — пробуем кэш
    if cache_client and cache == CacheMode.default:
        try:
            cached = cache_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except redis.RedisError:
            pass

    # 2. Идём в БД
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, title, description, price, duration "
                "FROM tours WHERE id = %s",
                (tour_id,),
            )
            result = cursor.fetchone()
    finally:
        conn.close()

    if result is None:
        raise HTTPException(status_code=404, detail="Tour not found")

    data = {
        "id": result[0],
        "title": result[1],
        "description": result[2],
        "price": float(result[3]),
        "duration": result[4],
    }

    # 3. Записываем в кэш (default и refresh — да, bypass — нет)
    if cache_client and cache != CacheMode.bypass:
        try:
            cache_client.setex(cache_key, CACHE_TTL, json.dumps(data))
        except redis.RedisError:
            pass

    return data
