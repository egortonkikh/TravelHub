#!/bin/bash
# ============================================================
# TravelHub — сценарий проверки API через curl
# Запускать после `docker compose up -d`
# ============================================================
set -euo pipefail

BASE="${BASE:-http://localhost}"

echo "========================================"
echo "  TravelHub — сценарий проверки API"
echo "========================================"
echo ""

# ---------- 1. Создать пользователя ----------
echo "▶ 1. Создаём пользователя Егор"
USER_RESP=$(curl -s -X POST "$BASE/api/users" \
  -H "Content-Type: application/json" \
  -d '{"name":"Егор","email":"egor@example.com"}')
echo "  Ответ: $USER_RESP"
USER_ID=$(echo "$USER_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "  → user_id = $USER_ID"
echo ""

# ---------- 2. Создать тур ----------
echo "▶ 2. Создаём тур «Москва — Питер»"
TOUR_RESP=$(curl -s -X POST "$BASE/api/tours" \
  -H "Content-Type: application/json" \
  -d '{"title":"Москва — Питер","description":"Тур по двум столицам, 5 дней","price":50000,"duration":5}')
echo "  Ответ: $TOUR_RESP"
TOUR_ID=$(echo "$TOUR_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "  → tour_id = $TOUR_ID"
echo ""

# ---------- 3. Создать бронирование ----------
echo "▶ 3. Создаём бронирование (user=$USER_ID, tour=$TOUR_ID)"
BOOKING_RESP=$(curl -s -X POST "$BASE/api/bookings" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":$USER_ID,\"tour_id\":$TOUR_ID}")
echo "  Ответ: $BOOKING_RESP"
BOOKING_ID=$(echo "$BOOKING_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "  → booking_id = $BOOKING_ID"
echo ""

# ---------- 4. Получить список пользователей ----------
echo "▶ 4. GET /api/users — список пользователей"
curl -s "$BASE/api/users" | python3 -m json.tool
echo ""

# ---------- 5. Получить список туров ----------
echo "▶ 5. GET /api/tours — список туров"
curl -s "$BASE/api/tours" | python3 -m json.tool
echo ""

# ---------- 6. Получить список бронирований ----------
echo "▶ 6. GET /api/bookings — список бронирований"
curl -s "$BASE/api/bookings" | python3 -m json.tool
echo ""

# ---------- 7. Получить конкретное бронирование ----------
echo "▶ 7. GET /api/bookings/$BOOKING_ID — конкретное бронирование"
curl -s "$BASE/api/bookings/$BOOKING_ID" | python3 -m json.tool
echo ""

# ---------- 8. Проверка inter-service взаимодействия ----------
echo "▶ 8. Создаём бронирование с несуществующим user (проверка inter-service)"
curl -s -o /dev/null -w "  HTTP статус: %{http_code} (ожидаем 404)\n" \
  -X POST "$BASE/api/bookings" \
  -H "Content-Type: application/json" \
  -d '{"user_id":99999,"tour_id":1}'
echo ""

# ---------- 9. Проверка персистентности ----------
echo "▶ 9. Проверка персистентности данных"
echo "  Текущие пользователи:"
curl -s "$BASE/api/users" | python3 -m json.tool
echo ""
echo "  [Действия для ручной проверки:]"
echo "    docker compose down          # остановить без удаления volume"
echo "    docker compose up -d         # поднять снова"
echo "    curl $BASE/api/users         # данные должны быть на месте"
echo ""

echo "========================================"
echo "  Сценарий завершён успешно ✅"
echo "========================================"
