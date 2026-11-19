import json
import os
import time

import pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://admin:admin@rabbitmq:5672/")
EXCHANGE_NAME = "bookings"
QUEUE_NAME = "notification-worker"
ROUTING_KEY = "booking.created"


def connect_with_retry(max_retries=10, delay=5):
    """Подключается к RabbitMQ с retry — ждёт, пока брокер поднимется."""
    for attempt in range(1, max_retries + 1):
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            print(f"Connected to RabbitMQ on attempt {attempt}")
            return connection
        except Exception as e:
            print(f"Attempt {attempt}/{max_retries}: RabbitMQ unavailable — {e}")
            time.sleep(delay)
    raise RuntimeError("Failed to connect to RabbitMQ after retries")


def main():
    print("Notification worker starting...")
    connection = connect_with_retry()
    channel = connection.channel()

    # Декларируем exchange (должен совпадать с booking-service)
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="direct", durable=True)

    # Декларируем очередь (durable — переживает рестарт RabbitMQ)
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key=ROUTING_KEY)

    def callback(ch, method, properties, body):
        try:
            event = json.loads(body)
            print(f"\n{'='*60}")
            print(f"Received booking.created event:")
            print(f"  Booking ID: {event.get('booking_id')}")
            print(f"  User ID:    {event.get('user_id')}")
            print(f"  Tour ID:    {event.get('tour_id')}")
            print(f"  Created at: {event.get('created_at')}")
            print(f"{'='*60}")

            # Здесь была бы реальная логика:
            # - отправить email пользователю
            # - обновить analytics
            # - уведомить менеджера
            # Пока — просто логируем

            # Acknowledge — сообщаем RabbitMQ что сообщение обработано
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print("Event processed and acknowledged.")
        except Exception as e:
            print(f"ERROR processing event: {e}")
            # Nack с requeue=False — сообщение пойдёт в dead-letter (если настроено)
            # или будет отброшено
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    # Ber Spiceri: не отправлять новое сообщение, пока не обработано предыдущее
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

    print(f"Worker listening on queue '{QUEUE_NAME}' for '{ROUTING_KEY}' events...")
    print("Press Ctrl+C to stop.")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\nStopping worker...")
        connection.close()


if __name__ == "__main__":
    main()
