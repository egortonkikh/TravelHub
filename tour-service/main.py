import os
import time

import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Tour Service")


class TourCreate(BaseModel):
    title: str
    description: str
    price: float
    duration: int


DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
DB_NAME = os.getenv("DB_NAME", "app")


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME,
    )


@app.on_event("startup")
def startup_event():
    time.sleep(3)
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
    print("✅ Таблица tours успешно создана или уже существует!")


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
    return {"id": new_id, "message": "Tour created successfully!"}


@app.get("/tours/{tour_id}")
def get_tour(tour_id: int):
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

    return {
        "id": result[0],
        "title": result[1],
        "description": result[2],
        "price": float(result[3]),
        "duration": result[4],
    }
