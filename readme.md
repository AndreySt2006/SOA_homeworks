# Архитектура Маркетплейса (C4 + Service Initialization)

## 1. C4 Container Диаграмма

@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml
LAYOUT_WITH_LEGEND()
title C4 Container Diagram: Marketplace System
Person(customer, "Pokupatel", "Ishet tovary, oformlyaet zakazy")
Person(seller, "Prodavec", "Upravlyaet tovarami")
System_Boundary(marketplace, "Marketplace System") {
    Container(gateway, "API Gateway", "Nginx/Kong", "Routit zaprosy")
    Container(user_svc, "User Service", "Python, FastAPI", "Profili i avtorizaciya")
    ContainerDb(user_db, "User DB", "PostgreSQL", "Baza yuzerov")
    Container(catalog_svc, "Catalog Service", "Python, FastAPI", "Katalog tovarov")
    ContainerDb(catalog_db, "Catalog DB", "PostgreSQL", "Baza tovarov")
    Container(order_svc, "Order Service", "Python, FastAPI", "Oformlenie zakazov")
    ContainerDb(order_db, "Order DB", "PostgreSQL", "Baza zakazov")
    Container(feed_svc, "Feed Service", "Python, FastAPI", "Lenta i poisk")
    ContainerDb(feed_db, "Feed Cache", "Redis", "Kesh dlya bystrogo poiska")
    Container(pay_svc, "Payment Service", "Python, FastAPI", "Oplaty")
    ContainerDb(pay_db, "Payment DB", "PostgreSQL", "Tranzakcii")
    Container(notif_svc, "Notification Service", "Python", "Otpravka pushey i pisem")
    ContainerQueue(broker, "Message Broker", "RabbitMQ", "Shina sobytiy")
}

Rel(customer, gateway, "Zaprosy", "HTTPS")
Rel(seller, gateway, "Zaprosy", "HTTPS")
Rel(gateway, user_svc, "Routing", "REST")
Rel(gateway, catalog_svc, "Routing", "REST")
Rel(gateway, order_svc, "Routing", "REST")
Rel(gateway, feed_svc, "Routing", "REST")
Rel(gateway, pay_svc, "Routing", "REST")
Rel(user_svc, user_db, "Chtenie/Zapis", "SQL")
Rel(catalog_svc, catalog_db, "Chtenie/Zapis", "SQL")
Rel(order_svc, order_db, "Chtenie/Zapis", "SQL")
Rel(feed_svc, feed_db, "Chtenie/Zapis", "Redis CLI")
Rel(pay_svc, pay_db, "Chtenie/Zapis", "SQL")
Rel(catalog_svc, broker, "Sobytiya kataloga", "AMQP")
Rel(order_svc, broker, "Sobytiya zakazov", "AMQP")
Rel(pay_svc, broker, "Sobytiya oplat", "AMQP")
Rel(broker, feed_svc, "Slushaet obnovleniya", "AMQP")
Rel(broker, pay_svc, "Slushaet dlya spisaniya", "AMQP")
Rel(broker, notif_svc, "Slushaet dlya uvedomleniy", "AMQP")

@enduml

## 2. Домены и распределение по сервисам

Логика разбиения простая — каждый домен отвечает за свою изолированную часть бизнеса и живет в своем микросервисе:
*   **Управление пользователями (User Service):** Регистрация, профили, авторизация покупателей и продавцов.
*   **Управление каталогом (Catalog Service):** Зона ответственности продавцов. Добавление товаров, изменение цен, остатков.
*   **Управление заказами (Order Service):** Создание заказа, отслеживание статуса (в сборке, в пути, доставлен).
*   **Персонализированная выдача (Feed Service):** Генерация ленты рекомендаций и быстрый поиск для покупателя.
*   **Учет платежей (Payment Service):** Обработка транзакций, списание денег, расчеты с продавцами.
*   **Уведомления (Notification Service):** Отправка писем и пушей по статусам заказов.

## 3. Границы владения данными и взаимодействие

В системе используется паттерн **Database-per-service**. 
*   Никаких общих баз. Каждый сервис имеет свою БД и полностью ей владеет.
*   Например, `Order Service` не может напрямую сделать SELECT из таблицы пользователей. Если ему нужны данные юзера, он запрашивает их у `User Service`.

**Способы взаимодействия:**
1.  **Синхронное (REST API):** Используется для запросов клиентов через API Gateway (например, получить корзину или профиль).
2.  **Асинхронное (Message Broker - RabbitMQ/Kafka):** Основной способ общения между сервисами. *Пример:* `Order Service` сохраняет заказ у себя в базе и кидает событие `OrderCreated` в брокер. `Payment Service` ловит это событие и списывает деньги, а `Notification Service` отправляет письмо.

## 4. Альтернативные варианты декомпозиции

**Вариант А: Монолитная архитектура (Модульный монолит)**
Всё пишется в одном приложении. База данных одна, но код разделен по папкам.

**Вариант Б: Сервис-ориентированная архитектура (SOA) с общей БД**
Код разбит на независимые сервисы, как у нас, но все они ходят в одну огромную базу данных (Shared Database).

## 5. Trade-off'ы вариантов

*   **Монолит (Вариант А):**
    *   *Плюсы:* Легко стартовать, всё в одном репозитории, не нужно возиться с брокерами сообщений и распределенными транзакциями.
    *   *Минусы:* Лента товаров (Feed) и Оплаты (Payments) требуют разных ресурсов. При наплыве пользователей на распродаже монолит упадет целиком, и перестанут работать даже независимые функции.
*   **SOA с общей БД (Вариант Б):**
    *   *Плюсы:* Нет проблем с консистентностью данных (можно просто делать JOIN таблиц из разных доменов).
    *   *Минусы:* База данных становится узким горлышком и единой точкой отказа. Если кто-то "криво" обновит таблицу каталога, могут сломаться заказы.

## 6. Обоснование финального выбора

Выбрана **Микросервисная архитектура с асинхронным взаимодействием**. 
*Почему:* Маркетплейс — это система с неравномерной нагрузкой. `Feed Service` (выдачу товаров) будут дергать постоянно тысячами RPS, поэтому там нужен быстрый кэш (например, Redis). `Payment Service` дергают реже, но там важна строгая надежность транзакций (PostgreSQL). Разделение на микросервисы позволяет масштабировать только те части, которые реально нагружены, и не ронять всю платформу из-за ошибки в одном модуле. Да, инфраструктура становится сложнее (нужен брокер, CI/CD), но это оправдано требованиями к стабильности маркетплейса.

## 7. Инструкция по запуску (Health-check)

В рамках ДЗ реализован базовый каркас одного из сервисов (User Service) для проверки инфраструктуры.

1. Убедитесь, что у вас установлен Docker и docker-compose.
2. Находясь в корне проекта (где лежит файл `docker-compose.yml`), выполните команду:
   ```bash
   docker-compose up -d --build