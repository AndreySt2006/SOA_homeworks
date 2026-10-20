import os
import time
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder
import jwt
from app.database import get_db
from app.models_orm import UserORM, ProductORM, PromoCodeORM, OrderORM, OrderItemORM, UserOperationORM
from app.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_roles, SECRET_KEY, ALGORITHM
)
from app.generated.models import (
    RegisterRequest, LoginRequest, RefreshRequest, TokenResponse,
    ProductCreate, ProductUpdate, ProductResponse, ProductPageResponse,
    PromoCodeCreate, PromoCodeResponse,
    OrderCreateRequest, OrderUpdateRequest, OrderResponse
)

app = FastAPI(
    title="Marketplace API",
    version="1.0.0",
    description="Бэкенд маркетплейса с контрактным подходом OpenAPI"
)
ORDER_LIMIT_SECONDS = int(os.getenv("ORDER_LIMIT_SECONDS", "5"))


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    start_time = time.time()
    user_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = int(payload.get("sub"))
        except Exception:
            pass
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)
    print(json.dumps({
        "user_id": user_id,
        "request_id": request_id,
        "method": request.method,
        "endpoint": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
        "timestamp": datetime.utcnow().isoformat()
    }, ensure_ascii=False))
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error_code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": "ERROR", "message": str(exc.detail), "details": None}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    fields = {".".join(str(x) for x in err["loc"] if x != "body"): err["msg"] for err in exc.errors()}
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Ошибка валидации входных данных",
            "details": fields
        }
    )


@app.post("/auth/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(UserORM).filter(UserORM.username == body.username).first()
    if existing:
        raise HTTPException(400, {"error_code": "USER_ALREADY_EXISTS", "message": "Пользователь уже существует"})
    new_user = UserORM(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role.value
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Пользователь успешно зарегистрирован", "user_id": new_user.id}


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserORM).filter(UserORM.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, {"error_code": "INVALID_CREDENTIALS", "message": "Неверный логин или пароль"})
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_access_token({"sub": str(user.id), "role": user.role}, expires_delta=timedelta(days=7))
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@app.post("/auth/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest):
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")
    except jwt.PyJWTError:
        raise HTTPException(401, {"error_code": "INVALID_REFRESH_TOKEN", "message": "Невалидный refresh-токен"})
    return {
        "access_token": create_access_token({"sub": str(user_id), "role": role}),
        "refresh_token": create_access_token({"sub": str(user_id), "role": role}, expires_delta=timedelta(days=7)),
        "token_type": "bearer"
    }


@app.get("/products", response_model=ProductPageResponse)
def get_products(
        page: int = Query(0, ge=0),
        size: int = Query(20, ge=1, le=100),
        status: Optional[str] = None,
        category: Optional[str] = None,
        db: Session = Depends(get_db),
        current_user: UserORM = Depends(get_current_user)
):
    query = db.query(ProductORM)
    if status:
        query = query.filter(ProductORM.status == status)
    if category:
        query = query.filter(ProductORM.category == category)
    total = query.count()
    items = query.offset(page * size).limit(size).all()
    return {"items": items, "totalElements": total, "page": page, "size": size}


@app.get("/products/{id}", response_model=ProductResponse)
def get_product(id: int, db: Session = Depends(get_db), current_user: UserORM = Depends(get_current_user)):
    product = db.query(ProductORM).filter(ProductORM.id == id).first()
    if not product:
        raise HTTPException(404, {"error_code": "PRODUCT_NOT_FOUND", "message": "Товар не найден"})
    return product


@app.post("/products", response_model=ProductResponse, status_code=201)
def create_product(
        body: ProductCreate,
        db: Session = Depends(get_db),
        current_user: UserORM = Depends(require_roles(["SELLER", "ADMIN"]))
):
    new_product = ProductORM(
        name=body.name,
        description=body.description,
        price=body.price,
        stock=body.stock,
        category=body.category,
        status=body.status.value,
        seller_id=current_user.id
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@app.put("/products/{id}", response_model=ProductResponse)
def update_product(
        id: int,
        body: ProductUpdate,
        db: Session = Depends(get_db),
        current_user: UserORM = Depends(require_roles(["SELLER", "ADMIN"]))
):
    product = db.query(ProductORM).filter(ProductORM.id == id).first()
    if not product:
        raise HTTPException(404, {"error_code": "PRODUCT_NOT_FOUND", "message": "Товар не найден"})
    if current_user.role == "SELLER" and product.seller_id != current_user.id:
        raise HTTPException(403, {"error_code": "ACCESS_DENIED", "message": "Можно менять только свои товары"})
    product.name = body.name
    product.description = body.description
    product.price = body.price
    product.stock = body.stock
    product.category = body.category
    product.status = body.status.value
    product.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(product)
    return product


@app.delete("/products/{id}", response_model=ProductResponse)
def delete_product(
        id: int,
        db: Session = Depends(get_db),
        current_user: UserORM = Depends(require_roles(["SELLER", "ADMIN"]))
):
    product = db.query(ProductORM).filter(ProductORM.id == id).first()
    if not product:
        raise HTTPException(404, {"error_code": "PRODUCT_NOT_FOUND", "message": "Товар не найден"})
    if current_user.role == "SELLER" and product.seller_id != current_user.id:
        raise HTTPException(403, {"error_code": "ACCESS_DENIED", "message": "Можно удалять только свои товары"})
    product.status = "ARCHIVED"
    product.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(product)
    return product


@app.post("/promo-codes", response_model=PromoCodeResponse, status_code=201)
def create_promo_code(
        body: PromoCodeCreate,
        db: Session = Depends(get_db),
        current_user: UserORM = Depends(require_roles(["SELLER", "ADMIN"]))
):
    promo = PromoCodeORM(
        code=body.code,
        discount_type=body.discount_type.value,
        discount_value=body.discount_value,
        min_order_amount=body.min_order_amount,
        max_uses=body.max_uses,
        current_uses=0,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        active=body.active if body.active is not None else True
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return promo


@app.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(
        body: OrderCreateRequest,
        db: Session = Depends(get_db),
        current_user: UserORM = Depends(require_roles(["USER", "ADMIN"]))
):
    now = datetime.now(timezone.utc)
    recent_op = db.query(UserOperationORM).filter(
        UserOperationORM.user_id == current_user.id,
        UserOperationORM.operation_type == "CREATE_ORDER"
    ).order_by(UserOperationORM.created_at.desc()).first()
    if recent_op:
        op_time = recent_op.created_at
        if op_time.tzinfo is None:
            op_time = op_time.replace(tzinfo=timezone.utc)
        if (now - op_time).total_seconds() < ORDER_LIMIT_SECONDS:
            raise HTTPException(429, {
                "error_code": "ORDER_LIMIT_EXCEEDED",
                "message": "Слишком частые запросы. Подождите немного."
            })
    active_order = db.query(OrderORM).filter(
        OrderORM.user_id == current_user.id,
        OrderORM.status.in_(["CREATED", "PAYMENT_PENDING"])
    ).first()
    if active_order:
        raise HTTPException(409, {
            "error_code": "ORDER_HAS_ACTIVE",
            "message": "У вас уже есть активный незавершенный заказ"
        })
    total_amount = 0.0
    order_items = []
    for item in body.items:
        product = db.query(ProductORM).filter(ProductORM.id == item.product_id).first()
        if not product or product.status != "ACTIVE":
            raise HTTPException(404, {
                "error_code": "PRODUCT_NOT_FOUND",
                "message": f"Товар {item.product_id} не найден или не активен"
            })
        if product.stock < item.quantity:
            raise HTTPException(409, {
                "error_code": "INSUFFICIENT_STOCK",
                "message": f"Недостаточно товара '{product.name}' на складе",
                "details": {
                    "product_id": product.id,
                    "requested": item.quantity,
                    "available": product.stock
                }
            })
        product.stock -= item.quantity
        price_snapshot = float(product.price)
        total_amount += price_snapshot * item.quantity
        order_items.append(OrderItemORM(
            product_id=product.id,
            quantity=item.quantity,
            price_at_order=price_snapshot
        ))
    discount_amount = 0.0
    promo_code_id = None
    if body.promo_code:
        promo = db.query(PromoCodeORM).filter(
            PromoCodeORM.code == body.promo_code,
            PromoCodeORM.active == True
        ).first()
        if not promo:
            raise HTTPException(422, {
                "error_code": "PROMO_CODE_INVALID",
                "message": "Промокод недействителен, истек или исчерпан"
            })
        valid_from = promo.valid_from
        valid_until = promo.valid_until
        if valid_from.tzinfo is None:
            valid_from = valid_from.replace(tzinfo=timezone.utc)
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        if promo.current_uses >= promo.max_uses or not (valid_from <= now <= valid_until):
            raise HTTPException(422, {
                "error_code": "PROMO_CODE_INVALID",
                "message": "Промокод недействителен, истек или исчерпан"
            })
        if total_amount < float(promo.min_order_amount):
            raise HTTPException(422, {
                "error_code": "PROMO_CODE_MIN_AMOUNT",
                "message": "Сумма заказа меньше минимальной для промокода"
            })
        if promo.discount_type == "PERCENTAGE":
            discount_amount = total_amount * (float(promo.discount_value) / 100.0)
            discount_amount = min(discount_amount, total_amount * 0.70)
        else:
            discount_amount = min(float(promo.discount_value), total_amount)
        promo.current_uses += 1
        promo_code_id = promo.id
    new_order = OrderORM(
        user_id=current_user.id,
        status="CREATED",
        promo_code_id=promo_code_id,
        total_amount=round(total_amount - discount_amount, 2),
        discount_amount=round(discount_amount, 2),
        items=order_items
    )
    db.add(new_order)
    db.add(UserOperationORM(user_id=current_user.id, operation_type="CREATE_ORDER"))
    db.commit()
    db.refresh(new_order)
    return new_order


@app.get("/orders/{id}", response_model=OrderResponse)
def get_order(
        id: int,
        db: Session = Depends(get_db),
        current_user: UserORM = Depends(require_roles(["USER", "ADMIN"]))
):
    order = db.query(OrderORM).filter(OrderORM.id == id).first()
    if not order:
        raise HTTPException(404, {"error_code": "ORDER_NOT_FOUND", "message": "Заказ не найден"})
    if current_user.role == "USER" and order.user_id != current_user.id:
        raise HTTPException(403, {"error_code": "ORDER_OWNERSHIP_VIOLATION", "message": "Чужой заказ"})
    return order


@app.put("/orders/{id}", response_model=OrderResponse)
def update_order(
        id: int,
        body: OrderUpdateRequest,
        db: Session = Depends(get_db),
        current_user: UserORM = Depends(require_roles(["USER", "ADMIN"]))
):
    order = db.query(OrderORM).filter(OrderORM.id == id).first()
    if not order:
        raise HTTPException(404, {"error_code": "ORDER_NOT_FOUND", "message": "Заказ не найден"})
    if current_user.role == "USER" and order.user_id != current_user.id:
        raise HTTPException(403, {"error_code": "ORDER_OWNERSHIP_VIOLATION", "message": "Чужой заказ"})
    if order.status != "CREATED":
        raise HTTPException(409, {"error_code": "INVALID_STATE_TRANSITION",
                                  "message": "Менять можно только заказ в статусе CREATED"})
    # Возвращаем старые товары обратно на склад
    for old_item in order.items:
        old_prod = db.query(ProductORM).filter(ProductORM.id == old_item.product_id).first()
        if old_prod:
            old_prod.stock += old_item.quantity
    order.items.clear()
    total_amount = 0.0
    for item in body.items:
        product = db.query(ProductORM).filter(ProductORM.id == item.product_id).first()
        if not product or product.status != "ACTIVE":
            raise HTTPException(404,
                                {"error_code": "PRODUCT_NOT_FOUND", "message": f"Товар {item.product_id} не найден"})
        if product.stock < item.quantity:
            raise HTTPException(409, {"error_code": "INSUFFICIENT_STOCK", "message": "Недостаточно товара на складе"})

        product.stock -= item.quantity
        price_snapshot = float(product.price)
        total_amount += price_snapshot * item.quantity
        order.items.append(OrderItemORM(product_id=product.id, quantity=item.quantity, price_at_order=price_snapshot))

    order.total_amount = round(total_amount - float(order.discount_amount), 2)
    order.updated_at = datetime.now(timezone.utc)
    db.add(UserOperationORM(user_id=current_user.id, operation_type="UPDATE_ORDER"))
    db.commit()
    db.refresh(order)
    return order


@app.post("/orders/{id}/cancel", response_model=OrderResponse)
def cancel_order(
        id: int,
        db: Session = Depends(get_db),
        current_user: UserORM = Depends(require_roles(["USER", "ADMIN"]))
):
    order = db.query(OrderORM).filter(OrderORM.id == id).first()
    if not order:
        raise HTTPException(404, {"error_code": "ORDER_NOT_FOUND", "message": "Заказ не найден"})
    if current_user.role == "USER" and order.user_id != current_user.id:
        raise HTTPException(403, {"error_code": "ORDER_OWNERSHIP_VIOLATION", "message": "Чужой заказ"})
    if order.status not in ["CREATED", "PAYMENT_PENDING"]:
        raise HTTPException(409,
                            {"error_code": "INVALID_STATE_TRANSITION", "message": "Этот заказ уже нельзя отменить"})
    for item in order.items:
        prod = db.query(ProductORM).filter(ProductORM.id == item.product_id).first()
        if prod:
            prod.stock += item.quantity
    if order.promo_code_id:
        promo = db.query(PromoCodeORM).filter(PromoCodeORM.id == order.promo_code_id).first()
        if promo and promo.current_uses > 0:
            promo.current_uses -= 1
    order.status = "CANCELED"
    order.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(order)
    return order