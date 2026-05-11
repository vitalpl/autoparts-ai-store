"""Скрипт для першого наповнення бази даних тестовими даними.

Запуск (один раз, після активації .venv):
    python seed.py
"""

from decimal import Decimal

from database import SessionLocal, init_db
from models import Avtozapchastyna, Katehoriya

# ---------------------------------------------------------------------------
# Тестові дані
# ---------------------------------------------------------------------------

SEED_DATA: list[dict] = [
    {
        "katehoriya": {"nazva": "Ходова частина", "opys": "Амортизатори, пружини, важелі, кульові опори"},
        "tovary": [
            {
                "artikul": "KYB-343250",
                "nazva": "Амортизатор задній",
                "brend": "Kayaba",
                "cina": Decimal("1850.00"),
                "kilkist_sklad": 12,
                "sumisnist": "Passat B6, Lanos, Focus",
                "opys": "Газомасляний амортизатор задньої осі. OEM: 1K0513029GH",
            },
            {
                "artikul": "KYB-334839",
                "nazva": "Амортизатор передній",
                "brend": "Kayaba",
                "cina": Decimal("2100.00"),
                "kilkist_sklad": 8,
                "sumisnist": "Passat B6, Audi A4 B7",
                "opys": "Газомасляний амортизатор передньої осі. OEM: 1K0413031BG",
            },
            {
                "artikul": "LEM-83501",
                "nazva": "Кульова опора нижня",
                "brend": "Lemforder",
                "cina": Decimal("720.00"),
                "kilkist_sklad": 20,
                "sumisnist": "Lanos, Sens, Nexia",
                "opys": "Кульова опора важеля підвіски. Посилена конструкція.",
            },
            {
                "artikul": "MEC-ME11450",
                "nazva": "Сайлентблок переднього важеля",
                "brend": "Meyle",
                "cina": Decimal("380.00"),
                "kilkist_sklad": 35,
                "sumisnist": "Golf IV, Passat B5, Octavia A5",
                "opys": "Гумово-металевий сайлентблок переднього нижнього важеля.",
            },
        ],
    },
    {
        "katehoriya": {"nazva": "Двигун та запалювання", "opys": "Свічки, фільтри, ремені, помпи, прокладки"},
        "tovary": [
            {
                "artikul": "BOS-0242236571",
                "nazva": "Свічка запалювання Platinum",
                "brend": "Bosch",
                "cina": Decimal("185.00"),
                "kilkist_sklad": 60,
                "sumisnist": "Lanos, Passat B6, Octavia, Megane",
                "opys": "Платинова свічка запалювання. Ресурс до 60 000 км.",
            },
            {
                "artikul": "NGK-BKUR6ET10",
                "nazva": "Свічка запалювання Iridium",
                "brend": "NGK",
                "cina": Decimal("310.00"),
                "kilkist_sklad": 40,
                "sumisnist": "Focus, Mondeo, Audi A4, Golf V",
                "opys": "Іридієва свічка запалювання. Ресурс до 100 000 км.",
            },
            {
                "artikul": "MAN-W71281",
                "nazva": "Фільтр масляний",
                "brend": "Mann-Filter",
                "cina": Decimal("220.00"),
                "kilkist_sklad": 50,
                "sumisnist": "Passat B6, Golf V, Octavia A5, Audi A4",
                "opys": "Масляний фільтр для двигунів VAG 1.6, 1.8, 2.0 TDI/TSI.",
            },
            {
                "artikul": "GAT-K015638XS",
                "nazva": "Комплект ГРМ з помпою",
                "brend": "Gates",
                "cina": Decimal("3200.00"),
                "kilkist_sklad": 6,
                "sumisnist": "Passat B6, Audi A4 B8, Octavia A5",
                "opys": "Комплект: ремінь ГРМ + натяжний ролик + помпа охолодження.",
            },
        ],
    },
    {
        "katehoriya": {"nazva": "Гальмівна система", "opys": "Колодки, диски, цилідри, шланги"},
        "tovary": [
            {
                "artikul": "BRM-P85072",
                "nazva": "Гальмівні колодки передні",
                "brend": "Brembo",
                "cina": Decimal("1450.00"),
                "kilkist_sklad": 15,
                "sumisnist": "Passat B6, Audi A4 B7, Audi A4 B8",
                "opys": "Передні гальмівні колодки з датчиком зносу. Ресурс 40 000 км.",
            },
            {
                "artikul": "FER-FDB1399",
                "nazva": "Гальмівні колодки передні",
                "brend": "Ferodo",
                "cina": Decimal("890.00"),
                "kilkist_sklad": 22,
                "sumisnist": "Lanos, Sens, Nexia, ZAZ",
                "opys": "Передні гальмівні колодки без датчика зносу.",
            },
            {
                "artikul": "TRW-DF4779",
                "nazva": "Гальмівний диск передній",
                "brend": "TRW",
                "cina": Decimal("1120.00"),
                "kilkist_sklad": 10,
                "sumisnist": "Focus II, Focus III, Mondeo IV",
                "opys": "Вентильований гальмівний диск. Діаметр 278 мм.",
            },
            {
                "artikul": "ATE-03990103",
                "nazva": "Головний гальмівний циліндр",
                "brend": "ATE",
                "cina": Decimal("2650.00"),
                "kilkist_sklad": 4,
                "sumisnist": "Golf IV, Golf V, Passat B5, Octavia",
                "opys": "Головний гальмівний циліндр з бачком. Оригінальна якість.",
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Логіка наповнення
# ---------------------------------------------------------------------------

def seed() -> None:
    init_db()
    db = SessionLocal()

    try:
        # Перевірка: якщо дані вже є — не дублюємо
        existing = db.query(Katehoriya).count()
        if existing > 0:
            print(f"База вже містить {existing} категорій. Seeding пропущено.")
            return

        total_products = 0

        for block in SEED_DATA:
            kat_data = block["katehoriya"]
            kat = Katehoriya(nazva=kat_data["nazva"], opys=kat_data["opys"])
            db.add(kat)
            db.flush()  # отримуємо kat.id без commit

            for t in block["tovary"]:
                tovar = Avtozapchastyna(
                    katehoriya_id=kat.id,
                    artikul=t["artikul"],
                    nazva=t["nazva"],
                    brend=t["brend"],
                    cina=t["cina"],
                    kilkist_sklad=t["kilkist_sklad"],
                    sumisnist=t["sumisnist"],
                    opys=t["opys"],
                )
                db.add(tovar)
                total_products += 1

        db.commit()
        print(f"Seeding завершено: додано {len(SEED_DATA)} категорій та {total_products} товарів.")

    except Exception as exc:
        db.rollback()
        print(f"Помилка під час seeding: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
