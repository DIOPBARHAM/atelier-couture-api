from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TypeVetement(Base):
    __tablename__ = "types_vetement"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    prix_base: Mapped[int] = mapped_column(Integer)
    delai_jours: Mapped[int] = mapped_column(Integer)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
