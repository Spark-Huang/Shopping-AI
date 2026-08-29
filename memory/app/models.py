"""ORM models and request DTOs for users, cart items, and orders."""

from urllib.parse import urlparse
from datetime import UTC, datetime
from math import isfinite
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)

from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    context = Column(String, default="")
    # Auth fields are nullable so legacy demo rows (created before accounts
    # existed) keep working; the first registration claims such a row.
    username = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    item = Column(String)
    amount = Column(Integer)
    price = Column(Float, nullable=True)
    url = Column(Text, nullable=True)
    __table_args__ = (
        Index("ux_cart_items_user_item", "user_id", "item", unique=True),
    )


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    item = Column(String)
    price = Column(Float, nullable=True)
    purchased_at = Column(DateTime)
    note = Column(Text, nullable=True)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id"), index=True, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    __table_args__ = (
        Index("ix_messages_user_created", "user_id", "created_at"),
        Index("ix_messages_user_session", "user_id", "session_id", "created_at"),
    )

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String(200), nullable=False, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class ContextUpdate(BaseModel):
    new_context: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class UserInfo(BaseModel):
    id: int
    username: str


class AuthResponse(BaseModel):
    token: str
    user: UserInfo


class MessageCreate(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=100000)


class MessageExtract(BaseModel):
    query: str
    response: str
    session_id: Optional[int] = None


class SessionCreate(BaseModel):
    title: str = Field(default="", max_length=200)


class SessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ItemUpdate(BaseModel):
    item: str
    amount: int
    price: Optional[float] = None
    url: Optional[str] = Field(default=None, max_length=2048)
    idempotent: bool = False

    @field_validator("url")
    @classmethod
    def validate_https_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if value == "":
            return value
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("url must use https and include a hostname")
        return value


class OrderCreate(BaseModel):
    item: str = Field(min_length=1, max_length=500)
    price: Optional[float] = None
    purchased_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if not isfinite(value) or value < 0:
            raise ValueError("price must be a finite, non-negative number")
        return value


class CheckoutItem(BaseModel):
    """One cart line to settle during checkout."""
    item: str = Field(min_length=1, max_length=500)
    price: Optional[float] = None

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if not isfinite(value) or value < 0:
            raise ValueError("price must be a finite, non-negative number")
        return value


class CheckoutRequest(BaseModel):
    """Multi-select checkout: turn the given cart lines into orders."""
    items: list[CheckoutItem] = Field(min_length=1)
