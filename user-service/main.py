import os
import time

import psycopg2
from fastapi import FastAPI, HTTPException
from psycopg2 import errors
from pydantic import BaseModel

app = FastAPI(title="User Service")


class UserCreate(BaseModel):
    name: str
    email: str


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
    time.sleep(3)  # Ждем 3 секунды, пока PostgreSQL проснется
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
    print("✅ Таблица users успешно создана или уже существует!")


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
    return {"id": new_id, "message": "User created successfully!"}


@app.get("/users/{user_id}")
def get_user(user_id: int):
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

    return {"id": result[0], "name": result[1], "email": result[2]}
