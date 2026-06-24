from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Завантажуємо змінні з .env найпершим кроком у системі,
# щоб уникнути помилок ініціалізації API-ключів у супутніх модулях
load_dotenv()

import json
import os
import random
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ai_service import AIService
from database import get_db, init_db
from models import Avtozapchastyna, Katehoriya, Korystuvach, Zamovlennya

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


# ─── Auth dependencies ────────────────────────────────────────────────────────
def get_current_user(
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> Korystuvach:
    """Dependency: повертає поточного авторизованого користувача або 401."""
    if not access_token:
        raise HTTPException(status_code=401, detail="Не авторизований")
    user_id = _decode_token(access_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Невалідний токен")
    user = db.get(Korystuvach, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Користувача не знайдено")
    return user


def get_admin_user(current_user: Korystuvach = Depends(get_current_user)) -> Korystuvach:
    """Dependency: повертає користувача тільки якщо він адміністратор, інакше 403."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ заборонено. Потрібні права адміністратора")
    return current_user


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


class ProductCreateRequest(BaseModel):
    nazva: str
    brend: str
    artikul: str
    cina: float
    kilkist_sklad: int = 0
    sumisnist: Optional[str] = None
    opys: Optional[str] = None
    katehoriya_id: Optional[int] = None


class ProductUpdateRequest(BaseModel):
    nazva: Optional[str] = None
    brend: Optional[str] = None
    artikul: Optional[str] = None
    cina: Optional[float] = None
    kilkist_sklad: Optional[int] = None
    sumisnist: Optional[str] = None
    opys: Optional[str] = None
    katehoriya_id: Optional[int] = None


class OrderItem(BaseModel):
    nazva: str
    brend: str
    artikul: str
    cina: float


class OrderCreateRequest(BaseModel):
    items: list[OrderItem]
    total: float
    buyer_name: str
    buyer_phone: str
    delivery_method: str = "nova_poshta"
    payment_method: str = "cod"


# ─── Page routes ─────────────────────────────────────────────────────────────
@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    # Завантажуємо категорії разом із їхніми товарами (eager load)
    categories = db.execute(
        select(Katehoriya).options(selectinload(Katehoriya.avtozapchastyny))
    ).scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"categories": categories},
    )


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


@app.get("/catalog/cat/{category_id}")
def category_page(
    category_id: int,
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
):
    """Сторінка категорії — показує товари з пагінацією (3 на сторінку)."""
    category = db.get(Katehoriya, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Категорія не знайдена")

    per_page = 3
    total_products = db.execute(
        select(func.count(Avtozapchastyna.id)).where(
            Avtozapchastyna.katehoriya_id == category_id
        )
    ).scalar() or 0

    products = db.execute(
        select(Avtozapchastyna)
        .where(Avtozapchastyna.katehoriya_id == category_id)
        .order_by(Avtozapchastyna.id)
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).scalars().all()

    total_pages = max(1, (total_products + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    return templates.TemplateResponse(
        request=request,
        name="category.html",
        context={
            "category": category,
            "products": products,
            "page": page,
            "total_pages": total_pages,
            "total_products": total_products,
            "per_page": per_page,
        },
    )


@app.get("/profile")
def profile_page(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html", context={})


@app.get("/roadside-help")
def roadside_help(request: Request):
    return templates.TemplateResponse(request=request, name="roadside_help.html", context={})


@app.get("/zsu-help")
def zsu_help(request: Request):
    return templates.TemplateResponse(request=request, name="zsu_help.html", context={})


@app.get("/admin")
def admin_page(
    request: Request,
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    """Сторінка адмін-панелі — доступна тільки для адміністраторів."""
    if not access_token:
        return RedirectResponse(url="/", status_code=302)
    user_id = _decode_token(access_token)
    if not user_id:
        return RedirectResponse(url="/", status_code=302)
    user = db.get(Korystuvach, user_id)
    if not user or not user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    products = db.execute(select(Avtozapchastyna)).scalars().all()
    categories = db.execute(select(Katehoriya)).scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "admin_user": user,
            "products": products,
            "categories": categories,
        },
    )


# ─── Auth endpoints ──────────────────────────────────────────────────────────
@app.post("/api/register")
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if db.execute(
        select(Korystuvach).where(Korystuvach.email == payload.email)
    ).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email вже використовується")

    # Спеціальний email для зручності тестування — отримує права адміна
    is_admin = payload.email.lower() == "admin@autoparts.com"

    user = Korystuvach(
        email=payload.email,
        imya=payload.name,
        parol_hash=pwd_context.hash(payload.password),
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_token(user.id)
    response.set_cookie(
        "access_token", token,
        httponly=True, max_age=TOKEN_EXPIRE_DAYS * 86400, samesite="lax",
    )
    return {"user": {"id": user.id, "name": user.imya, "email": user.email, "model_avto": user.model_avto, "is_admin": user.is_admin}}


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
    return {"user": {"id": user.id, "name": user.imya, "email": user.email, "model_avto": user.model_avto, "is_admin": user.is_admin}}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"ok": True}


@app.get("/api/me")
def me(current_user: Korystuvach = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.imya,
        "email": current_user.email,
        "model_avto": current_user.model_avto,
        "is_admin": current_user.is_admin,
    }


# ─── Profile / Garage ────────────────────────────────────────────────────────
@app.post("/api/profile/garage")
def update_garage(
    payload: GarageRequest,
    current_user: Korystuvach = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.model_avto = payload.model_avto.strip()
    db.commit()
    return {"ok": True, "model_avto": current_user.model_avto}


# ─── Orders ──────────────────────────────────────────────────────────────────
@app.post("/api/orders/create")
def create_order(
    payload: OrderCreateRequest,
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    order_number = f"AP-{random.randint(1000, 9999)}"

    order_data = {
        "order_number": order_number,
        "buyer_name": payload.buyer_name,
        "buyer_phone": payload.buyer_phone,
        "delivery_method": payload.delivery_method,
        "payment_method": payload.payment_method,
        "items": [i.model_dump() for i in payload.items],
    }

    # Save to DB for authenticated users only (guest orders have nullable FK issue)
    if access_token:
        uid = _decode_token(access_token)
        if uid:
            user = db.get(Korystuvach, uid)
            if user:
                order = Zamovlennya(
                    korystuvach_id=user.id,
                    zahalna_suma=payload.total,
                    status="Прийнято",
                    items_json=json.dumps(order_data, ensure_ascii=False),
                )
                db.add(order)
                db.commit()

    return {"status": "success", "order_id": order_number}


@app.get("/api/orders")
def get_orders(
    current_user: Korystuvach = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = db.execute(
        select(Zamovlennya)
        .where(Zamovlennya.korystuvach_id == current_user.id)
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


# ─── Admin: Products CRUD ─────────────────────────────────────────────────────
@app.get("/api/admin/products")
def admin_list_products(
    _: Korystuvach = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Повертає всі товари для адмін-панелі."""
    rows = db.execute(select(Avtozapchastyna)).scalars().all()
    return [
        {
            "id": p.id,
            "nazva": p.nazva,
            "brend": p.brend,
            "artikul": p.artikul,
            "cina": float(p.cina),
            "kilkist_sklad": p.kilkist_sklad,
            "sumisnist": p.sumisnist,
            "opys": p.opys,
            "katehoriya_id": p.katehoriya_id,
        }
        for p in rows
    ]


@app.post("/api/admin/products", status_code=201)
def admin_create_product(
    payload: ProductCreateRequest,
    admin: Korystuvach = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Додає новий товар до каталогу."""
    # Якщо katehoriya_id не вказано — використати першу доступну категорію
    katehoriya_id = payload.katehoriya_id
    if not katehoriya_id:
        first_cat = db.execute(select(Katehoriya)).scalars().first()
        if not first_cat:
            raise HTTPException(status_code=400, detail="Немає жодної категорії в базі даних")
        katehoriya_id = first_cat.id

    if db.execute(
        select(Avtozapchastyna).where(Avtozapchastyna.artikul == payload.artikul)
    ).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Товар з таким артикулом вже існує")

    product = Avtozapchastyna(
        nazva=payload.nazva,
        brend=payload.brend,
        artikul=payload.artikul,
        cina=payload.cina,
        kilkist_sklad=payload.kilkist_sklad,
        sumisnist=payload.sumisnist,
        opys=payload.opys,
        katehoriya_id=katehoriya_id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"ok": True, "id": product.id}


@app.put("/api/admin/products/{product_id}")
def admin_update_product(
    product_id: int,
    payload: ProductUpdateRequest,
    _: Korystuvach = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Оновлює поля вказаного товару (тільки передані поля)."""
    product = db.get(Avtozapchastyna, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не знайдено")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return {"ok": True}


@app.delete("/api/admin/products/{product_id}")
def admin_delete_product(
    product_id: int,
    _: Korystuvach = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Видаляє товар з каталогу за ідентифікатором."""
    product = db.get(Avtozapchastyna, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не знайдено")
    db.delete(product)
    db.commit()
    return {"ok": True}

