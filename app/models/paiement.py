from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ModePaiement


class Paiement(Base):
    __tablename__ = "paiements"

    id: Mapped[int] = mapped_column(primary_key=True)
    commande_id: Mapped[int] = mapped_column(
        ForeignKey("commandes.id", ondelete="CASCADE"), index=True
    )
    montant: Mapped[int] = mapped_column(Integer)
    mode: Mapped[ModePaiement] = mapped_column(
        Enum(ModePaiement, native_enum=False, length=20)
    )
    reference: Mapped[str | None] = mapped_column(String(100))
    date_paiement: Mapped[date] = mapped_column(Date, default=date.today)
    enregistre_par_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    commande: Mapped["Commande"] = relationship(back_populates="paiements")
