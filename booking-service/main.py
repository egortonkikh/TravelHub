import json
import os
from contextlib import asynccontextmanager

import pika
import psycopg2
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
DB_NAME = os.getenv("DB_NAME", "app")

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8000")
TOUR_SERVICE_URL = os.getenv("TOUR_SERVICE_URL", "http://tour-service:8000")
REQUEST_TIMEOUT = 5

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://admin:admin@rabbitmq:5672/")
EXCHANGE_NAME = "bookings"
ROUTING_KEY = "booking.created"


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME,
    )


def get_rabbitmq_channel():
    """Создаёт подключение к RabbitMQ и возвращает channel + exchange declaration."""
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="direct", durable=True)
    return connection, channel


def publish_booking_event(booking_data: dict):
    """Публикует событие booking.created в RabbitMQ."""
    try:
        connection, channel = get_rabbitmq_channel()
        try:
            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=ROUTING_KEY,
                body=json.dumps(booking_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # persistent message
                    content_type="application/json",
                ),
            )
            print(f"Published event: {booking_data}")
        finally:
            connection.close()
    except Exception as e:
        # Брокер недоступен — не падаем. Бронирование уже сохранено в БД.
        print(f"WARNING: failed to publish event to RabbitMQ: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS bookings (
                    id SERIAL PRIMARY KEY,
                    user_id INT NOT NULL,
                    tour_id INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        conn.commit()
    finally:
        conn.close()
    print("bookings table ready")
    yield


app = FastAPI(title="Booking Service", lifespan=lifespan)


class BookingCreate(BaseModel):
    user_id: int
    tour_id: int


def check_exists(url: str, not_found_detail: str, unavailable_detail: str):
    """Проверяет через HTTP, что сущность существует в другом сервисе."""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail=unavailable_detail)

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=not_found_detail)
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=unavailable_detail)


@app.post("/bookings")
def create_booking(booking: BookingCreate):
    # 1. Проверяем пользователя через user-service (HTTP, синхронно)
    check_exists(
        f"{USER_SERVICE_URL}/users/{booking.user_id}",
        f"User with id {booking.user_id} not found",
        "User service is unavailable",
    )

    # 2. Проверяем тур через tour-service (HTTP, синхронно)
    check_exists(
        f"{TOUR_SERVICE_URL}/tours/{booking.tour_id}",
        f"Tour with id {booking.tour_id} not found",
        "Tour service is unavailable",
    )

    # 3. Сохраняем бронирование в БД
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO bookings (user_id, tour_id) VALUES (%s, %s) "
                "RETURNING id, created_at",
                (booking.user_id, booking.tour_id),
            )
            row = cursor.fetchone()
            new_id = row[0]
            created_at = str(row[1])
        conn.commit()
    finally:
        conn.close()

    # 4. Публикуем событие booking.created в RabbitMQ (асинхронная обработка)
    event_data = {
        "event": "booking.created",
        "booking_id": new_id,
        "user_id": booking.user_id,
        "tour_id": booking.tour_id,
        "created_at": created_at,
    }
    publish_booking_event(event_data)

    return {
        "id": new_id,
        "message": "Booking created successfully!",
        "booking": booking.model_dump(),
        "event_published": True,
    }


@app.get("/bookings")
def list_bookings():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, user_id, tour_id, created_at "
                "FROM bookings ORDER BY id"
            )
            rows = cursor.fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "tour_id": r[2],
            "created_at": str(r[3]),
        }
        for r in rows
    ]


@app.get("/bookings/{booking_id}")
def get_booking(booking_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, user_id, tour_id, created_at "
                "FROM bookings WHERE id = %s",
                (booking_id,),
            )
            result = cursor.fetchone()
    finally:
        conn.close()

    if result is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    return {
        "id": result[0],
        "user_id": result[1],
        "tour_id": result[2],
        "created_at": str(result[3]),
    }
