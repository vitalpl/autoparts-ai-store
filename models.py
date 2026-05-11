from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# 1. Korystuvach — зареєстрований користувач магазину
# ---------------------------------------------------------------------------
class Korystuvach(Base):
    __tablename__ = "korystuvachi"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    imya: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    parol_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    data_rejestraciyi: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Один користувач — багато замовлень; при видаленні користувача видаляються й замовлення
    zamovlennya: Mapped[List["Zamovlennya"]] = relationship(
        back_populates="korystuvach",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# 2. Katehoriya — категорія автозапчастин (напр. "Гальмівна система")
# ---------------------------------------------------------------------------
class Katehoriya(Base):
    __tablename__ = "katehoriyi"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nazva: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    opys: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Одна категорія — багато запчастин
    avtozapchastyny: Mapped[List["Avtozapchastyna"]] = relationship(
        back_populates="katehoriya",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# 3. Avtozapchastyna — конкретна автозапчастина в каталозі
# ---------------------------------------------------------------------------
class Avtozapchastyna(Base):
    __tablename__ = "avtozapchastyny"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    artikul: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    nazva: Mapped[str] = mapped_column(String(255), nullable=False)
    brend: Mapped[str] = mapped_column(String(100), nullable=False)
    cina: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    kilkist_sklad: Mapped[int] = mapped_column(default=0, nullable=False)
    # Сумісність — текстове поле для AI-помічника (напр. "Volkswagen Passat B6, Audi A4 B8")
    sumisnist: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opys: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    katehoriya_id: Mapped[int] = mapped_column(
        ForeignKey("katehoriyi.id", ondelete="CASCADE"), nullable=False
    )

    katehoriya: Mapped["Katehoriya"] = relationship(back_populates="avtozapchastyny")

    # Запчастина може бути у багатьох позиціях замовлень
    pozytsiyi_zamovlen: Mapped[List["ZamovlenyyTovar"]] = relationship(
        back_populates="zapchastyna",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# 4. Zamovlennya — замовлення покупця
# ---------------------------------------------------------------------------
class Zamovlennya(Base):
    __tablename__ = "zamovlennya"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    korystuvach_id: Mapped[int] = mapped_column(
        ForeignKey("korystuvachi.id", ondelete="CASCADE"), nullable=False
    )
    data_zamovlennya: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    zahalna_suma: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Нове")

    korystuvach: Mapped["Korystuvach"] = relationship(back_populates="zamovlennya")

    # Одне замовлення — багато позицій товарів; при видаленні замовлення позиції видаляються
    tovary: Mapped[List["ZamovlenyyTovar"]] = relationship(
        back_populates="zamovlennya",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# 5. ZamovlenyyTovar — проміжна таблиця Many-to-Many (замовлення ↔ запчастина)
# ---------------------------------------------------------------------------
class ZamovlenyyTovar(Base):
    __tablename__ = "zamovleni_tovary"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    zamovlennya_id: Mapped[int] = mapped_column(
        ForeignKey("zamovlennya.id", ondelete="CASCADE"), nullable=False
    )
    zapchastyna_id: Mapped[int] = mapped_column(
        ForeignKey("avtozapchastyny.id", ondelete="CASCADE"), nullable=False
    )
    kilkist: Mapped[int] = mapped_column(nullable=False, default=1)
    # Фіксує ціну на момент покупки, щоб зміна ціни в каталозі не впливала на архів
    cina_prodazhu: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    zamovlennya: Mapped["Zamovlennya"] = relationship(back_populates="tovary")
    zapchastyna: Mapped["Avtozapchastyna"] = relationship(back_populates="pozytsiyi_zamovlen")

