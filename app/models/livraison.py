from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ModeLivraison, StatutLivraison


class Livraison(Base):
    __tablename__ = "livraisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    commande_id: Mapped[int] = mapped_column(
        ForeignKey("commandes.id", ondelete="CASCADE"), unique=True
    )
    mode: Mapped[ModeLivraison] = mapped_column(
        Enum(ModeLivraison, native_enum=False, length=20)
    )
    adresse: Mapped[str | None] = mapped_column(String(255))
    livreur: Mapped[str | None] = mapped_column(String(100))
    date_prevue: Mapped[date | None] = mapped_column(Date)
    date_effective: Mapped[date | None] = mapped_column(Date)
    statut: Mapped[StatutLivraison] = mapped_column(
        Enum(StatutLivraison, native_enum=False, length=20),
        default=StatutLivraison.planifiee,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    commande: Mapped["Commande"] = relationship(back_populates="livraison")
