from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Завантажуємо змінні з .env найпершим кроком у системі,
# щоб уникнути помилок ініціалізації API-ключів у супутніх модулях
load_dotenv()

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles  # 📥 Імпорт для підтримки роздачі статики
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ai_service import AIService
from database import get_db, init_db
from models import Avtozapchastyna


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Викликається один раз при запуску сервера — створює та ініціалізує таблиці БД."""
    init_db()
    yield


# Ініціалізація FastAPI додатка з підтримкою асинхронного життєвого циклу
app = FastAPI(title="AutoParts AI Store", lifespan=lifespan)

# 🛠️ МОНТУВАННЯ СТАТИКИ:
# Дозволяє роздавати картинки (напр. head.png), CSS та JS з локальної папки /static/
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ініціалізація шаблонізатора Jinja2 для рендерингу вебінтерфейсу
templates = Jinja2Templates(directory="templates")

# Створення єдиного екземпляра AI-сервісу на рівні всього додатка
_ai_service = AIService()


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def home(request: Request):
    """Рендеринг головної сторінки інтернет-магазину."""
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


@app.post("/api/chat")
async def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    Асинхронний REST API ендпоінт для обробки повідомлень клієнта.
    Здійснює запит до Gemini, семантичний аналіз тексту та вибірку сумісних товарів з SQLite.
    """
    # Отримуємо структуровану відповідь від нашого ШІ-сервісу
    ai_response = await _ai_service.consult_client(payload.message)

    reply: str = ai_response.get("reply", "")
    keyword: str | None = ai_response.get("search_keyword")
    compatibility: str | None = ai_response.get("compatibility")

    products = []

    # Якщо ШІ успішно виділив ключове слово для пошуку, робимо запит до БД
    if keyword:
        stmt = select(Avtozapchastyna).where(
            or_(
                Avtozapchastyna.nazva.ilike(f"%{keyword}%"),
                Avtozapchastyna.opys.ilike(f"%{keyword}%"),
            )
        )

        # Додатково фільтруємо за сумісністю авто (якщо бренд/модель розпізнано)
        if compatibility:
            stmt = stmt.where(Avtozapchastyna.sumisnist.ilike(f"%{compatibility}%"))

        stmt = stmt.limit(6)
        rows = db.execute(stmt).scalars().all()

        # Серіалізуємо результати SQLAlchemy в JSON-сумісний формат
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