from fastapi import FastAPI, Header, HTTPException
from datetime import UTC, datetime
from typing import Optional
import time

from .auth import (
    create_token,
    hash_password,
    user_id_from_authorization,
    verify_password,
)
from .database import SessionLocal, initialize_database
from .models import (
    CartItem,
    ContextUpdate,
    ItemUpdate,
    LoginRequest,
    Order,
    OrderCreate,
    RegisterRequest,
    User,
)

app = FastAPI()

initialize_database()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _auth_response(user: User) -> dict:
    return {
        "token": create_token(user.id, user.username),
        "user": {"id": user.id, "username": user.username},
    }


@app.post("/auth/register")
async def register(request: RegisterRequest):
    """Create an account and return a JWT.

    The very first registration claims the legacy demo row (user id 1)
    so its cart, orders, and context carry over to the new account.
    """
    with SessionLocal() as db:
        if db.query(User).filter(User.username == request.username).first():
            raise HTTPException(status_code=409, detail="Username already taken")

        user = None
        already_registered = (
            db.query(User).filter(User.password_hash.isnot(None)).first() is not None
        )
        if not already_registered:
            legacy = db.query(User).filter(User.id == 1).first()
            if legacy:
                legacy.username = request.username
                legacy.password_hash = hash_password(request.password)
                user = legacy
        if user is None:
            user = User(
                username=request.username,
                password_hash=hash_password(request.password),
                context="",
            )
            db.add(user)
        db.commit()
        db.refresh(user)
        return _auth_response(user)


@app.post("/auth/login")
async def login(request: LoginRequest):
    """Verify credentials and return a JWT for the user."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == request.username).first()
        if (
            not user
            or not user.password_hash
            or not verify_password(request.password, user.password_hash)
        ):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        return _auth_response(user)


@app.get("/auth/me")
async def me(authorization: Optional[str] = Header(default=None)):
    """Return the account behind the bearer token."""
    user_id = user_id_from_authorization(authorization)
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="Unknown user")
        return {"id": user.id, "username": user.username}


def _cart_item_dict(item: CartItem) -> dict:
    return {"item": item.item, "amount": item.amount, "price": item.price, "url": item.url}


def _order_dict(order: Order) -> dict:
    return {
        "id": order.id,
        "item": order.item,
        "price": order.price,
        "purchased_at": order.purchased_at.isoformat() if order.purchased_at else None,
        "note": order.note,
    }


@app.get("/user/{user_id}")
async def get_user(user_id: int):
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        cart_items = db.query(CartItem).filter(CartItem.user_id == user_id).all()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"id": user.id, "context": user.context, "cart": [_cart_item_dict(item) for item in cart_items]}


@app.get("/user/{user_id}/cart")
async def report_cart(user_id: int):
    with SessionLocal() as db:
        cart_items = db.query(CartItem).filter(CartItem.user_id == user_id).all()
        if not cart_items:
            return {
                "user_id": user_id,
                "cart": []
            }
        return {
            "user_id": user_id,
            "cart": [_cart_item_dict(item) for item in cart_items]
        }


@app.get("/user/{user_id}/context")
async def get_context(user_id: int):
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {
                "user_id": user_id,
                "context": ""
            }
        return {
            "user_id": user_id,
            "context": user.context
        }


@app.post("/user/{user_id}/cart/add")
async def add_to_cart(user_id: int, item_update: ItemUpdate):
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.add(User(id=user_id, context=""))
        item = item_update.item
        amount = item_update.amount
        price = item_update.price
        url = item_update.url
        cart_item = db.query(CartItem).filter(CartItem.user_id == user_id, CartItem.item == item).first()
        if cart_item:
            cart_item.amount = amount if item_update.idempotent else cart_item.amount + amount
            # Refresh price if the caller provides a newer value; URL is
            # canonical and an empty string clears a stale catalog value.
            if price is not None:
                cart_item.price = price
            if url is not None:
                cart_item.url = url or None
        else:
            cart_item = CartItem(user_id=user_id, item=item, amount=amount, price=price, url=url)
            db.add(cart_item)
        db.commit()
    return {
        "user_id": user_id,
        "message": (
            f"In response to the user's request, I have set the quantity of '{item}' to {amount}."
            if item_update.idempotent
            else f"In response to the user's request, I have added {amount} of '{item}' to their cart."
        )
        }


@app.post("/user/{user_id}/orders")
async def create_order(user_id: int, order_create: OrderCreate):
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.add(User(id=user_id, context=""))
        order = Order(
            user_id=user_id,
            item=order_create.item,
            price=order_create.price,
            purchased_at=order_create.purchased_at or datetime.now(UTC),
            note=order_create.note,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return {"order": _order_dict(order)}


@app.get("/user/{user_id}/orders")
async def list_orders(user_id: int):
    with SessionLocal() as db:
        orders = (
            db.query(Order)
            .filter(Order.user_id == user_id)
            .order_by(Order.purchased_at.desc(), Order.id.desc())
            .all()
        )
        return {"user_id": user_id, "orders": [_order_dict(order) for order in orders]}


@app.post("/user/{user_id}/cart/remove")
async def remove_cart(user_id: int, item_update: ItemUpdate):
    with SessionLocal() as db:
        item = item_update.item
        amount = item_update.amount
        cart_item = db.query(CartItem).filter(CartItem.user_id == user_id, CartItem.item == item).first()
        if not cart_item:
            raise HTTPException(status_code=404, detail="Item not in cart")
        if cart_item.amount <= amount:
            db.delete(cart_item)
        else:
            cart_item.amount -= amount
        db.commit()
    return {
        "user_id": user_id,
        "message": f"In response to the user's request, I have removed {amount} of '{item}' from cart."
        }


@app.post("/user/{user_id}/cart/clear")
async def clear_cart(user_id: int):
    with SessionLocal() as db:
        cart_items = db.query(CartItem).filter(CartItem.user_id == user_id).all()
        if not cart_items:
            raise HTTPException(status_code=404, detail="No items found in cart")
        for item in cart_items:
            db.delete(item)
        db.commit()
    return {
        "user_id": user_id,
        "message": f"In response to the user's request, the cart for user {user_id} has been deleted."
        }


@app.post("/user/{user_id}/context/add")
async def add_context(user_id: int, context_update: ContextUpdate):
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            user = User(id=user_id, context=context_update.new_context)
            db.add(user)
        else:
            user.context += " " + context_update.new_context
        db.commit()
    return {
        "user_id": user_id,
        "message": "Context updated successfully"
        }


@app.post("/user/{user_id}/context/replace")
async def replace_context(user_id: int, context_update: ContextUpdate):
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            user = User(id=user_id, context=context_update.new_context)
            db.add(user)
        else:
            user.context = context_update.new_context
        db.commit()
    return {
        "user_id": user_id,
        "message": "Context updated successfully"
        }


@app.post("/user/{user_id}/context/clear")
async def clear_context(user_id: int):
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        db.delete(user)
        db.commit()
    return {
        "user_id": user_id,
        "message": f"In response to the user's request, context for user {user_id} has been deleted."
        }


@app.post("/user/{user_id}/clear")
async def clear_user(user_id: int):
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        db.query(CartItem).filter(CartItem.user_id == user_id).delete()
        if user:
            db.delete(user)
        db.commit()
    return {
        "user_id": user_id,
        "message": f"In response to the user's request, deleted cart and context for user {user_id}"
        }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0"
    }
