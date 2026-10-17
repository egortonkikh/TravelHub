import os
import time

import psycopg2
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Booking Service")


class BookingCreate(BaseModel):
    user_id: int
    tour_id: int


# Настройки БД (те же самые)
DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
DB_NAME = os.getenv("DB_NAME", "app")

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8000")
TOUR_SERVICE_URL = os.getenv("TOUR_SERVICE_URL", "http://tour-service:8000")
REQUEST_TIMEOUT = 5


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME,
    )


@app.on_event("startup")
def startup_event():
    time.sleep(3)  # Ждем, пока PostgreSQL проснется
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
    print("✅ Таблица bookings успешно создана или уже существует!")


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
    # 1. Проверяем пользователя (обращаемся к user-service по имени в Docker)
    check_exists(
        f"{USER_SERVICE_URL}/users/{booking.user_id}",
        f"User with id {booking.user_id} not found",
        "User service is unavailable",
    )

    # 2. Проверяем тур (обращаемся к tour-service)
    check_exists(
        f"{TOUR_SERVICE_URL}/tours/{booking.tour_id}",
        f"Tour with id {booking.tour_id} not found",
        "Tour service is unavailable",
    )

    # 3. Если всё существует - сохраняем бронирование в БД
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO bookings (user_id, tour_id) VALUES (%s, %s) "
                "RETURNING id",
                (booking.user_id, booking.tour_id),
            )
            new_id = cursor.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    return {
        "id": new_id,
        "message": "Booking created successfully!",
        "booking": booking.dict(),
    }


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
