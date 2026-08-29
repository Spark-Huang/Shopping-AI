import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime
from typing import Optional

from fastapi import FastAPI, Header, HTTPException

from .auth import (
    create_token,
    hash_password,
    user_id_from_authorization,
    verify_password,
)
from .cognee_client import CogneeClient
from .database import SessionLocal, initialize_database
from .models import (
    CartItem,
    CheckoutRequest,
    ContextUpdate,
    ItemUpdate,
    LoginRequest,
    Message,
    MessageCreate,
    MessageExtract,
    Order,
    OrderCreate,
    RegisterRequest,
    Session,
    SessionCreate,
    SessionUpdate,
    User,
)

app = FastAPI()

initialize_database()

logger = logging.getLogger(__name__)
cognee_client = CogneeClient.from_env()
_background_extraction_tasks: set[asyncio.Future] = set()


def _log_extraction_failure(task: asyncio.Future) -> None:
    exception = task.exception()
    if exception is not None:
        logger.error("memory | background cognee extraction failed: %s", exception)


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
    return {
        "item": item.item,
        "amount": item.amount,
        "price": item.price,
        "url": item.url,
        "image": item.image,
    }


def _order_dict(order: Order) -> dict:
    return {
        "id": order.id,
        "item": order.item,
        "price": order.price,
        "purchased_at": order.purchased_at.isoformat() if order.purchased_at else None,
        "note": order.note,
    }


PRODUCTS_MARKER_PATTERN = re.compile(
    r"(?:^|\n)<!--PRODUCTS:(?P<products>.*?)-->(?:\n|$)", re.DOTALL
)


def _message_dict(message: Message) -> dict:
    content = message.content
    products = None
    match = PRODUCTS_MARKER_PATTERN.search(content)
    if match:
        try:
            parsed = json.loads(match.group("products"))
            if isinstance(parsed, dict):
                products = parsed
                content = PRODUCTS_MARKER_PATTERN.sub("", content).strip()
        except json.JSONDecodeError:
            products = None
    return {
        "id": message.id,
        "user_id": message.user_id,
        "role": message.role,
        "content": content,
        "products": products,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "session_id": message.session_id,
    }


def _session_dict(session: Session) -> dict:
    return {
        "id": session.id,
        "user_id": session.user_id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


def _get_scoped_session(db, user_id: int, authorization: Optional[str], session_id: int) -> Session:
    user_id_from_authorization(authorization)
    chat_session = (
        db.query(Session)
        .filter(Session.id == session_id, Session.user_id == user_id)
        .first()
    )
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
    return chat_session


def _touch_session(db, chat_session: Session) -> None:
    chat_session.updated_at = datetime.now(UTC)
    db.commit()


def _format_context(base_context: str, semantic_memory: list[str]) -> str:
    long_term_memory = "\n".join(
        f"Long-term memory: {memory}"
        for memory in semantic_memory
        if memory.strip()
    )
    return "\n".join(part for part in (base_context, long_term_memory) if part.strip())


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


@app.get("/user/{user_id}/memory")
async def get_semantic_memory(user_id: int, query: str):
    retrieved = await cognee_client.retrieve(query)
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        base_context = user.context if user else ""
    with SessionLocal() as db:
        recent_messages = (
            db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(10)
            .all()
        )
    return {
        "user_id": user_id,
        "semantic_memory": retrieved,
        "context": _format_context(base_context, retrieved),
        "recent_messages": [_message_dict(message) for message in reversed(recent_messages)],
    }


@app.post("/user/{user_id}/messages/extract")
async def add_and_extract_message(
    user_id: int,
    request: MessageExtract,
    authorization: Optional[str] = Header(default=None),
):
    session_id = request.session_id
    messages = [
        Message(user_id=user_id, role="user", content=request.query, session_id=session_id),
        Message(user_id=user_id, role="assistant", content=request.response, session_id=session_id),
    ]
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.add(User(id=user_id, context=""))
        chat_session = None
        if session_id is not None:
            chat_session = _get_scoped_session(db, user_id, authorization, session_id)
        db.add_all(messages)
        db.commit()
        message_ids = [message.id for message in messages]
        if session_id is not None:
            _touch_session(db, chat_session)

    transcript = f"User {user_id}\nUser: {request.query}\nAssistant: {request.response}"
    extraction_scheduled = False
    if cognee_client.settings.embedding_enabled:
        task = asyncio.create_task(cognee_client.extract(transcript))
        _background_extraction_tasks.add(task)
        task.add_done_callback(_background_extraction_tasks.discard)
        task.add_done_callback(_log_extraction_failure)
        extraction_scheduled = True

    return {
        "user_id": user_id,
        "message_ids": message_ids,
        "extraction_scheduled": extraction_scheduled,
    }


@app.get("/user/{user_id}/sessions")
async def list_sessions(user_id: int, authorization: Optional[str] = Header(default=None)):
    user_id_from_authorization(authorization)
    with SessionLocal() as db:
        sessions = (
            db.query(Session)
            .filter(Session.user_id == user_id)
            .order_by(Session.updated_at.desc(), Session.id.desc())
            .all()
        )
    return {"user_id": user_id, "sessions": [_session_dict(item) for item in sessions]}


@app.post("/user/{user_id}/sessions")
async def create_session(user_id: int, request: SessionCreate, authorization: Optional[str] = Header(default=None)):
    user_id_from_authorization(authorization)
    with SessionLocal() as db:
        if not db.query(User).filter(User.id == user_id).first():
            db.add(User(id=user_id, context=""))
        chat_session = Session(user_id=user_id, title=request.title)
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)
    return _session_dict(chat_session)


@app.get("/user/{user_id}/sessions/{session_id}")
async def read_session(user_id: int, session_id: int, authorization: Optional[str] = Header(default=None)):
    with SessionLocal() as db:
        chat_session = _get_scoped_session(db, user_id, authorization, session_id)
    return _session_dict(chat_session)


@app.patch("/user/{user_id}/sessions/{session_id}")
async def update_session_title(user_id: int, session_id: int, request: SessionUpdate, authorization: Optional[str] = Header(default=None)):
    with SessionLocal() as db:
        chat_session = _get_scoped_session(db, user_id, authorization, session_id)
        chat_session.title = request.title
        _touch_session(db, chat_session)
        db.refresh(chat_session)
    return _session_dict(chat_session)


@app.delete("/user/{user_id}/sessions/{session_id}")
async def delete_session(user_id: int, session_id: int, authorization: Optional[str] = Header(default=None)):
    with SessionLocal() as db:
        chat_session = _get_scoped_session(db, user_id, authorization, session_id)
        db.query(Message).filter(
            Message.user_id == user_id,
            Message.session_id == session_id,
        ).delete(synchronize_session=False)
        db.delete(chat_session)
        db.commit()
    return {"message": "Session deleted"}


@app.get("/user/{user_id}/sessions/{session_id}/messages")
async def list_session_messages(user_id: int, session_id: int, authorization: Optional[str] = Header(default=None)):
    with SessionLocal() as db:
        _get_scoped_session(db, user_id, authorization, session_id)
        messages = (
            db.query(Message)
            .filter(Message.user_id == user_id, Message.session_id == session_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .all()
        )
    return {
        "user_id": user_id,
        "session_id": session_id,
        "messages": [_message_dict(message) for message in messages],
    }


@app.get("/user/{user_id}/messages")
async def list_messages(user_id: int):
    with SessionLocal() as db:
        messages = (
            db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(200)
            .all()
        )
    return {"user_id": user_id, "messages": [_message_dict(message) for message in reversed(messages)]}


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
        image = item_update.image
        cart_item = db.query(CartItem).filter(CartItem.user_id == user_id, CartItem.item == item).first()
        if cart_item:
            cart_item.amount = amount if item_update.idempotent else cart_item.amount + amount
            # Refresh price if the caller provides a newer value; URL is
            # canonical and an empty string clears a stale catalog value.
            if price is not None:
                cart_item.price = price
            if url is not None:
                cart_item.url = url or None
            if image is not None:
                cart_item.image = image or None
        else:
            cart_item = CartItem(
                user_id=user_id,
                item=item,
                amount=amount,
                price=price,
                url=url,
                image=image,
            )
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


@app.post("/user/{user_id}/checkout")
async def checkout(user_id: int, checkout_request: CheckoutRequest):
    """Settle the selected cart lines: record one order per line, then clear them from the cart.

    The order price is the line total (unit price x cart amount) so the
    orders summary reflects actual spending; the amount is kept in the note.
    """
    created_orders: list[Order] = []
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            db.add(User(id=user_id, context=""))
        for entry in checkout_request.items:
            cart_item = (
                db.query(CartItem)
                .filter(CartItem.user_id == user_id, CartItem.item == entry.item)
                .first()
            )
            if not cart_item:
                raise HTTPException(status_code=404, detail=f"Item not in cart: {entry.item}")
            unit_price = entry.price if entry.price is not None else cart_item.price
            total_price = unit_price * cart_item.amount if unit_price is not None else None
            order = Order(
                user_id=user_id,
                item=cart_item.item,
                price=total_price,
                purchased_at=datetime.now(UTC),
                note=f"Checked out x{cart_item.amount}",
            )
            db.add(order)
            created_orders.append(order)
            db.delete(cart_item)
        db.commit()
        for order in created_orders:
            db.refresh(order)
    return {
        "user_id": user_id,
        "orders": [_order_dict(order) for order in created_orders],
        "message": f"In response to the user's request, I have checked out {len(checkout_request.items)} item(s) and created orders.",
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
