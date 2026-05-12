from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Завантажуємо змінні з .env найпершим кроком у системі,
# щоб уникнути помилок ініціалізації API-ключів у супутніх модулях
load_dotenv()

import json
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ai_service import AIService
from database import get_db, init_db
from models import Avtozapchastyna, Korystuvach, Zamovlennya

# ─── Auth config ────────────────────────────────────────────────────────────
SECRET_KEY: str = os.environ.get("SECRET_KEY", "autoparts-dev-secret-key-2026")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _create_token(user_id: int) -> str:
    exp = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None


# ─── Lifespan ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Викликається один раз при запуску сервера — створює та ініціалізує таблиці БД."""
    init_db()
    yield


app = FastAPI(title="AutoParts AI Store", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
_ai_service = AIService()


# ─── Pydantic schemas ────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class GarageRequest(BaseModel):
    model_avto: str


class OrderItem(BaseModel):
    nazva: str
    brend: str
    artikul: str
    cina: float


class OrderCreateRequest(BaseModel):
    items: list[OrderItem]
    total: float


# ─── Page routes ─────────────────────────────────────────────────────────────
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.get("/promotions")
def promotions(request: Request):
    return templates.TemplateResponse(request=request, name="promotions.html", context={})


@app.get("/delivery")
def delivery(request: Request):
    return templates.TemplateResponse(request=request, name="delivery.html", context={})


@app.get("/payment")
def payment(request: Request):
    return templates.TemplateResponse(request=request, name="payment.html", context={})


@app.get("/returns")
def returns(request: Request):
    return templates.TemplateResponse(request=request, name="returns.html", context={})


@app.get("/help")
def help_page(request: Request):
    return templates.TemplateResponse(request=request, name="help.html", context={})


@app.get("/contacts")
def contacts(request: Request):
    return templates.TemplateResponse(request=request, name="contacts.html", context={})


@app.get("/catalog/brake-pads")
def brake_pads(request: Request):
    return templates.TemplateResponse(request=request, name="brake_pads.html", context={})


@app.get("/catalog/drum-brake-pads")
def drum_brake_pads(request: Request):
    return templates.TemplateResponse(request=request, name="drum_pads.html", context={})


@app.get("/profile")
def profile_page(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html", context={})


# ─── Auth endpoints ──────────────────────────────────────────────────────────
@app.post("/api/register")
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if db.execute(
        select(Korystuvach).where(Korystuvach.email == payload.email)
    ).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email вже використовується")

    user = Korystuvach(
        email=payload.email,
        imya=payload.name,
        parol_hash=pwd_context.hash(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_token(user.id)
    response.set_cookie(
        "access_token", token,
        httponly=True, max_age=TOKEN_EXPIRE_DAYS * 86400, samesite="lax",
    )
    return {"user": {"id": user.id, "name": user.imya, "email": user.email, "model_avto": user.model_avto}}


@app.post("/api/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.execute(
        select(Korystuvach).where(Korystuvach.email == payload.email)
    ).scalar_one_or_none()
    if not user or not pwd_context.verify(payload.password, user.parol_hash):
        raise HTTPException(status_code=401, detail="Невірний email або пароль")

    token = _create_token(user.id)
    response.set_cookie(
        "access_token", token,
        httponly=True, max_age=TOKEN_EXPIRE_DAYS * 86400, samesite="lax",
    )
    return {"user": {"id": user.id, "name": user.imya, "email": user.email, "model_avto": user.model_avto}}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"ok": True}


@app.get("/api/me")
def me(
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    if not access_token:
        raise HTTPException(status_code=401, detail="Не авторизований")
    user_id = _decode_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Невалідний токен")
    user = db.get(Korystuvach, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Користувача не знайдено")
    return {"id": user.id, "name": user.imya, "email": user.email, "model_avto": user.model_avto}


# ─── Profile / Garage ────────────────────────────────────────────────────────
@app.post("/api/profile/garage")
def update_garage(
    payload: GarageRequest,
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    if not access_token:
        raise HTTPException(status_code=401, detail="Не авторизований")
    user_id = _decode_token(access_token)
    user = db.get(Korystuvach, user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизований")
    user.model_avto = payload.model_avto.strip()
    db.commit()
    return {"ok": True, "model_avto": user.model_avto}


# ─── Orders ──────────────────────────────────────────────────────────────────
@app.post("/api/orders/create")
def create_order(
    payload: OrderCreateRequest,
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    if not access_token:
        raise HTTPException(status_code=401, detail="Не авторизований")
    user_id = _decode_token(access_token)
    user = db.get(Korystuvach, user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизований")

    order = Zamovlennya(
        korystuvach_id=user.id,
        zahalna_suma=payload.total,
        status="Прийнято",
        items_json=json.dumps(
            [i.model_dump() for i in payload.items], ensure_ascii=False
        ),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"ok": True, "order_id": order.id}


@app.get("/api/orders")
def get_orders(
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    if not access_token:
        raise HTTPException(status_code=401, detail="Не авторизований")
    user_id = _decode_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Не авторизований")

    orders = db.execute(
        select(Zamovlennya)
        .where(Zamovlennya.korystuvach_id == user_id)
        .order_by(Zamovlennya.data_zamovlennya.desc())
    ).scalars().all()

    return [
        {
            "id": o.id,
            "date": o.data_zamovlennya.strftime("%d.%m.%Y %H:%M"),
            "total": float(o.zahalna_suma),
            "status": o.status,
            "items": json.loads(o.items_json) if o.items_json else [],
        }
        for o in orders
    ]


# ─── Chat ─────────────────────────────────────────────────────────────────────
@app.post("/api/chat")
async def chat_endpoint(
    payload: ChatRequest,
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    """
    Асинхронний REST API ендпоінт для обробки повідомлень клієнта.
    Якщо AI не розпізнав сумісність, але у авторизованого користувача заповнений
    'Мій Гараж' — підставляє модель його авто автоматично.
    """
    ai_response = await _ai_service.consult_client(payload.message)

    reply: str = ai_response.get("reply", "")
    keyword: str | None = ai_response.get("search_keyword")
    compatibility: str | None = ai_response.get("compatibility")

    # Якщо AI не розпізнав авто, але юзер авторизований і має "Мій Гараж" — підставляємо
    if keyword and not compatibility and access_token:
        user_id = _decode_token(access_token)
        if user_id:
            garage_user = db.get(Korystuvach, user_id)
            if garage_user and garage_user.model_avto:
                compatibility = garage_user.model_avto

    products = []

    if keyword:
        stmt = select(Avtozapchastyna).where(
            or_(
                Avtozapchastyna.nazva.ilike(f"%{keyword}%"),
                Avtozapchastyna.opys.ilike(f"%{keyword}%"),
            )
        )
        if compatibility:
            stmt = stmt.where(Avtozapchastyna.sumisnist.ilike(f"%{compatibility}%"))

        stmt = stmt.limit(6)
        rows = db.execute(stmt).scalars().all()

        products = [
            {
                "id": p.id,
                "nazva": p.nazva,
                "brend": p.brend,
                "cina": float(p.cina),
                "artikul": p.artikul,
                "kilkist_sklad": p.kilkist_sklad,
            }
            for p in rows
        ]

    return {"reply": reply, "products": products}

