# Flight Booking System (Python, student style)

Домашнее задание №3 — gRPC + Redis на Python (FastAPI + grpcio).

## Запуск

```bash
docker-compose up --build
```

- Booking Service REST: http://localhost:8000/docs
- Flight Service gRPC: localhost:50051
- Postgres Booking: localhost:5433
- Postgres Flight: localhost:5434
- Redis Sentinel: localhost:26379

## Что реализовано (на 10 баллов)

1-4: gRPC контракт, ER 3NF, PostgreSQL + миграции (create_all), REST + gRPC, взаимодействие.

5: Транзакции + SELECT FOR UPDATE, идемпотентность ReserveSeats.

6: API Key в metadata, UNAUTHENTICATED.

7: Redis cache-aside (flight + search), TTL 5 мин, инвалидация, логи hit/miss. Sentinel.

8: Retry (tenacity) 3 попытки, exponential, только UNAVAILABLE/DEADLINE, идемпотентность.

9: Redis Sentinel (master + replica + sentinel).

10: Circuit Breaker (простой класс + логи состояний), параметры из env, 503 при OPEN.

См. er_diagram.md для схемы.
