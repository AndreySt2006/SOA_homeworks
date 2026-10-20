from sqlalchemy import Column, BigInteger, String, Numeric, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class UserORM(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)

class ProductORM(Base):
    __tablename__ = "products"
    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(4000), nullable=True)
    price = Column(Numeric(12, 2), nullable=False)
    stock = Column(Integer, nullable=False)
    category = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    seller_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class PromoCodeORM(Base):
    __tablename__ = "promo_codes"
    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False)
    discount_type = Column(String(20), nullable=False)
    discount_value = Column(Numeric(12, 2), nullable=False)
    min_order_amount = Column(Numeric(12, 2), nullable=False, default=0)
    max_uses = Column(Integer, nullable=False)
    current_uses = Column(Integer, nullable=False, default=0)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    active = Column(Boolean, nullable=False, default=True)

class OrderORM(Base):
    __tablename__ = "orders"
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    status = Column(String(30), nullable=False)
    promo_code_id = Column(BigInteger, ForeignKey("promo_codes.id"), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=False)
    discount_amount = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    items = relationship("OrderItemORM", back_populates="order", cascade="all, delete-orphan")

class OrderItemORM(Base):
    __tablename__ = "order_items"
    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(BigInteger, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price_at_order = Column(Numeric(12, 2), nullable=False)
    order = relationship("OrderORM", back_populates="items")

class UserOperationORM(Base):
    __tablename__ = "user_operations"
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    operation_type = Column(String(30), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)