from contextlib import asynccontextmanager
from dotenv import load_dotenv
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
from database import get_db, init_db, SessionLocal
from models import Avtozapchastyna, Katehoriya, Korystuvach, Zamovlennya

# ─── Auth & Config ──────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "autoparts-dev-secret-key-2026")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def _create_token(user_id: int) -> str:
    exp = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

def _decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError): return None

def init_admin():
    db = SessionLocal()
    admin_email = "admin@autoparts.com"
    if not db.query(Korystuvach).filter(Korystuvach.email == admin_email).first():
        hashed = pwd_context.hash("admin123")
        admin = Korystuvach(email=admin_email, imya="Адміністратор", parol_hash=hashed, is_admin=True)
        db.add(admin); db.commit()
    db.close()

# ─── Lifespan ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        init_admin()
        yield
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        raise e

app = FastAPI(title="AutoParts AI Store", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
_ai_service = AIService()

# ─── Schemas & Routes ───────────────────────────────────────────────────────
class ChatRequest(BaseModel): message: str
class RegisterRequest(BaseModel): email: str; name: str; password: str
class LoginRequest(BaseModel): email: str; password: str
class ProductCreateRequest(BaseModel): nazva: str; brend: str; artikul: str; cina: float; kilkist_sklad: int = 0; katehoriya_id: Optional[int] = None

@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    cats = db.execute(select(Katehoriya).options(selectinload(Katehoriya.avtozapchastyny))).scalars().all()
    return templates.TemplateResponse(request=request, name="index.html", context={"categories": cats})

@app.get("/api/me")
def me(access_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    user_id = _decode_token(access_token) if access_token else None
    user = db.get(Korystuvach, user_id) if user_id else None
    if not user: raise HTTPException(status_code=401, detail="Не авторизований")
    return {"id": user.id, "name": user.imya, "is_admin": user.is_admin}

@app.post("/api/register")
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if db.execute(select(Korystuvach).where(Korystuvach.email == payload.email)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email вже зайнятий")
    user = Korystuvach(email=payload.email, imya=payload.name, parol_hash=pwd_context.hash(payload.password), is_admin=(payload.email == "admin@autoparts.com"))
    db.add(user); db.commit(); db.refresh(user)
    response.set_cookie("access_token", _create_token(user.id), httponly=True)
    return {"user": {"id": user.id, "name": user.imya, "is_admin": user.is_admin}}

@app.post("/api/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.execute(select(Korystuvach).where(Korystuvach.email == payload.email)).scalar_one_or_none()
    if not user or not pwd_context.verify(payload.password, user.parol_hash):
        raise HTTPException(status_code=401, detail="Невірні дані")
    response.set_cookie("access_token", _create_token(user.id), httponly=True)
    return {"user": {"id": user.id, "name": user.imya, "is_admin": user.is_admin}}

@app.post("/api/admin/products")
async def admin_create_product(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        print(f"DEBUG: Отримані дані з фронтенду: {data}")
        
        prod = Avtozapchastyna(
    nazva=data.get("nazva"),
    brend=data.get("brend"),
    artikul=data.get("artikul"),
    cina=float(data.get("cina", 0)),
    kilkist_sklad=int(data.get("kilkist_sklad", 0)),
    # Якщо прийшов пустий рядок або None, перетворимо на None
    katehoriya_id=int(data["katehoriya_id"]) if data.get("katehoriya_id") and data["katehoriya_id"] != "" else None
)
        db.add(prod)
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        print(f"ERROR: {str(e)}") # Це виведе реальну причину в логи Render
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin")
def admin_page(request: Request, access_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    user_id = _decode_token(access_token) if access_token else None
    user = db.get(Korystuvach, user_id) if user_id else None
    if not user or not user.is_admin: return RedirectResponse(url="/")
    return templates.TemplateResponse(request=request, name="admin.html", context={"admin_user": user, "products": db.execute(select(Avtozapchastyna)).scalars().all(), "categories": db.execute(select(Katehoriya)).scalars().all()})

@app.get("/{full_path:path}")
def catch_all(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")