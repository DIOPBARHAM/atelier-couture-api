from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StatutCommande


class Commande(Base):
    __tablename__ = "commandes"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    mesure_id: Mapped[int | None] = mapped_column(ForeignKey("mesures.id"))
    statut: Mapped[StatutCommande] = mapped_column(
        Enum(StatutCommande, native_enum=False, length=20),
        default=StatutCommande.en_attente,
    )
    date_commande: Mapped[date] = mapped_column(Date, default=date.today)
    date_livraison_prevue: Mapped[date] = mapped_column(Date)
    date_livraison_reelle: Mapped[date | None] = mapped_column(Date)
    remise: Mapped[int] = mapped_column(Integer, default=0)
    montant_total: Mapped[int] = mapped_column(Integer, default=0)
    montant_paye: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    cree_par_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="commandes")
    mesure: Mapped["Mesure | None"] = relationship()
    lignes: Mapped[list["LigneCommande"]] = relationship(
        back_populates="commande",
        cascade="all, delete-orphan",
        order_by="LigneCommande.id",
    )
    paiements: Mapped[list["Paiement"]] = relationship(
        back_populates="commande",
        cascade="all, delete-orphan",
        order_by="Paiement.id",
    )
    historique: Mapped[list["HistoriqueStatut"]] = relationship(
        back_populates="commande",
        cascade="all, delete-orphan",
        order_by="HistoriqueStatut.id",
    )
    livraison: Mapped["Livraison | None"] = relationship(
        back_populates="commande", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def solde(self) -> int:
        return self.montant_total - self.montant_paye


class LigneCommande(Base):
    __tablename__ = "lignes_commande"

    id: Mapped[int] = mapped_column(primary_key=True)
    commande_id: Mapped[int] = mapped_column(
        ForeignKey("commandes.id", ondelete="CASCADE"), index=True
    )
    type_vetement_id: Mapped[int] = mapped_column(ForeignKey("types_vetement.id"))
    description: Mapped[str | None] = mapped_column(String(255))
    quantite: Mapped[int] = mapped_column(Integer)
    prix_unitaire: Mapped[int] = mapped_column(Integer)

    commande: Mapped["Commande"] = relationship(back_populates="lignes")
    type_vetement: Mapped["TypeVetement"] = relationship()


class HistoriqueStatut(Base):
    __tablename__ = "historique_statuts"

    id: Mapped[int] = mapped_column(primary_key=True)
    commande_id: Mapped[int] = mapped_column(
        ForeignKey("commandes.id", ondelete="CASCADE"), index=True
    )
    ancien_statut: Mapped[StatutCommande | None] = mapped_column(
        Enum(StatutCommande, native_enum=False, length=20)
    )
    nouveau_statut: Mapped[StatutCommande] = mapped_column(
        Enum(StatutCommande, native_enum=False, length=20)
    )
    commentaire: Mapped[str | None] = mapped_column(Text)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"))
    date_changement: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    commande: Mapped["Commande"] = relationship(back_populates="historique")
