from sqlalchemy.orm import declarative_base , Mapped , mapped_column, relationship
from sqlalchemy import String , Integer ,  ForeignKey , UniqueConstraint, Table, Column, Text, DateTime, func, Boolean, CheckConstraint, Numeric
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime
from decimal import Decimal




Base = declarative_base()

## TABLES D'ASSOCIATION ##

chunk_erreur = Table("chunk_erreur",
    Base.metadata , 
     Column(Integer, ForeignKey("erreur.id_erreur", ondelete="CASCADE"), nullable=False, name="id_erreur", primary_key=True ),
    Column(Integer, ForeignKey("chunk.id_chunk", ondelete="CASCADE"), nullable=False, name="id_chunk", primary_key=True)
    )

chunk_modele = Table("chunk_modele",
                     Base.metadata,
                     Column(Integer, ForeignKey("chunk.id_chunk", ondelete="CASCADE"), nullable=False, name="id_chunk", primary_key=True),
                     Column(String(50), ForeignKey("modele.modele"), nullable=False, name="modele", primary_key=True)
                     )
    
    
## TABLES MÉTIER ##

class Modele (Base):
    
    __tablename__ = "modele"
    
    modele : Mapped[str] = mapped_column(String(50), primary_key=True)
    type : Mapped[str | None] = mapped_column(String(150), nullable=True)
    
    rel_erreur = relationship("Erreur", back_populates="rel_modele") 
    rel_chunk_modele = relationship("Chunk" , secondary=chunk_modele, back_populates="rel_chunk_modele")


class Document (Base) : 
    
    __tablename__ = 'document'      
    
    id_document : Mapped[int] = mapped_column(Integer, primary_key=True)
    source : Mapped[str] = mapped_column(String(255), nullable=False, unique=True)     # fichier d'origine, identifie le document
    categorie : Mapped[str] = mapped_column(String(50), nullable=False, index=True)    # Manuel, FAQ... (droits de lecture des rôles)
    titre : Mapped[str] = mapped_column(String(150), nullable=False)
    version : Mapped[str | None] = mapped_column(String(150), nullable=True)
    empreinte : Mapped[str | None] = mapped_column(String(64), nullable=True)          # sha256 du fichier ingéré : inchangé = pas de retraitement
    date_enr : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now() )
    
    rel_chunk = relationship("Chunk", back_populates="rel_document" , cascade="all, delete-orphan")
    
class Chunk(Base):
    
    __tablename__ = "chunk"
    
    id_chunk : Mapped[int] = mapped_column(Integer, primary_key=True)
    id_document : Mapped[int] = mapped_column(Integer, ForeignKey("document.id_document", ondelete="CASCADE"), nullable=False)
    position_chunk : Mapped[int] = mapped_column(Integer, nullable=True)
    contenu : Mapped[str] = mapped_column(Text, nullable= False)
    vecteur : Mapped[list[float]] = mapped_column(Vector(1024), nullable=True)
    pages : Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)      # pages du document d'origine (pdf)
    
    rel_chunk_erreur = relationship("Erreur", secondary=chunk_erreur, back_populates="rel_chunk_erreur")
    rel_chunk_modele = relationship("Modele", secondary=chunk_modele , back_populates="rel_chunk_modele")
    rel_document = relationship("Document", back_populates="rel_chunk")
    
class Erreur(Base) :
    
    __tablename__ = "erreur"
    
    
    id_erreur : Mapped[int] = mapped_column(Integer , primary_key=True)
    modele : Mapped[str] = mapped_column(String(50), ForeignKey("modele.modele"), nullable=False)
    code_erreur : Mapped[str] = mapped_column(String(20), nullable=False)
    signification : Mapped[str] = mapped_column(String(150), nullable=False)
    conduite : Mapped[str] = mapped_column(String(255), nullable=False)
    intervention : Mapped[str] = mapped_column(String(255), nullable=False)
    
    rel_modele = relationship("Modele",  back_populates="rel_erreur")
    rel_chunk_erreur = relationship("Chunk", secondary= chunk_erreur , back_populates="rel_chunk_erreur")
    
    __table_args__ = (UniqueConstraint("modele","code_erreur"),)


## UTILISATEURS ##

ROLES = ("admin", "conseiller")      # type de compte : droits de gestion (a ne pas confondre avec les rôles d'accès)

utilisateur_role = Table("utilisateur_role",
                         Base.metadata,
                         Column(Integer, ForeignKey("utilisateur.id_utilisateur", ondelete="CASCADE"), nullable=False, name="id_utilisateur", primary_key=True),
                         Column(Integer, ForeignKey("role.id_role", ondelete="CASCADE"), nullable=False, name="id_role", primary_key=True)
                         )


class Role(Base) :
    """rôle d'accès a la documentation, attribué aux comptes par un administrateur :
    un compte voit les documents des catégories de tous ses rôles (les administrateurs voient tout)"""

    __tablename__ = "role"

    id_role : Mapped[int] = mapped_column(Integer, primary_key=True)
    nom : Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description : Mapped[str | None] = mapped_column(String(255), nullable=True)
    categories : Mapped[list[str]] = mapped_column(ARRAY(String(50)), nullable=False, server_default="{}")
    date_creation : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    rel_utilisateur = relationship("Utilisateur", secondary=utilisateur_role, back_populates="rel_role")


class Utilisateur(Base) :

    __tablename__ = "utilisateur"

    id_utilisateur : Mapped[int] = mapped_column(Integer, primary_key=True)
    identifiant : Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    nom : Mapped[str] = mapped_column(String(150), nullable=False)
    mot_de_passe : Mapped[str] = mapped_column(String(255), nullable=False)          # empreinte scrypt, jamais le mot de passe
    role : Mapped[str] = mapped_column(String(20), nullable=False, server_default="conseiller")
    actif : Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    date_creation : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    derniere_connexion : Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rel_conversation = relationship("Conversation", back_populates="rel_utilisateur", cascade="all, delete-orphan", passive_deletes=True)
    rel_jeton = relationship("Jeton", back_populates="rel_utilisateur", cascade="all, delete-orphan", passive_deletes=True)
    rel_role = relationship("Role", secondary=utilisateur_role, back_populates="rel_utilisateur", order_by="Role.nom")

    __table_args__ = (CheckConstraint(f"role IN {ROLES}", name="ck_utilisateur_role"),)


class Jeton(Base) :
    """jeton de session remis a la connexion ; seule son empreinte est stockée"""

    __tablename__ = "jeton"

    id_jeton : Mapped[int] = mapped_column(Integer, primary_key=True)
    id_utilisateur : Mapped[int] = mapped_column(Integer, ForeignKey("utilisateur.id_utilisateur", ondelete="CASCADE"), nullable=False, index=True)
    empreinte : Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    date_creation : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expiration : Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    rel_utilisateur = relationship("Utilisateur", back_populates="rel_jeton")


class Connexion(Base) :
    """journal des tentatives de connexion (réussies ou non) ; garde l'identifiant saisi même si l'utilisateur est supprimé"""

    __tablename__ = "connexion"

    id_connexion : Mapped[int] = mapped_column(Integer, primary_key=True)
    id_utilisateur : Mapped[int | None] = mapped_column(Integer, ForeignKey("utilisateur.id_utilisateur", ondelete="SET NULL"), nullable=True, index=True)
    identifiant : Mapped[str] = mapped_column(String(50), nullable=False)
    date : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    succes : Mapped[bool] = mapped_column(Boolean, nullable=False)
    adresse_ip : Mapped[str | None] = mapped_column(String(45), nullable=True)


## CONVERSATIONS ##

class Conversation(Base) :

    __tablename__ = "conversation"

    id_conversation : Mapped[int] = mapped_column(Integer, primary_key=True)
    id_utilisateur : Mapped[int] = mapped_column(Integer, ForeignKey("utilisateur.id_utilisateur", ondelete="CASCADE"), nullable=False, index=True)
    titre : Mapped[str] = mapped_column(String(150), nullable=False)
    date_creation : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    date_maj : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    rel_utilisateur = relationship("Utilisateur", back_populates="rel_conversation")
    rel_message = relationship("Message", back_populates="rel_conversation", order_by="Message.id_message",
                               cascade="all, delete-orphan", passive_deletes=True)


class Message(Base) :
    """un message de la conversation. role : 'user' ou 'assistant' (les rôles de l'API du LLM)"""

    __tablename__ = "message"

    id_message : Mapped[int] = mapped_column(Integer, primary_key=True)
    id_conversation : Mapped[int] = mapped_column(Integer, ForeignKey("conversation.id_conversation", ondelete="CASCADE"), nullable=False, index=True)
    role : Mapped[str] = mapped_column(String(20), nullable=False)
    contenu : Mapped[str] = mapped_column(Text, nullable=False)
    sources : Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)       # sources citées par la réponse
    modele_llm : Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_entree : Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_sortie : Mapped[int | None] = mapped_column(Integer, nullable=True)
    cout : Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)      # en dollars, tel que facturé par OpenRouter
    contact_sav : Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")   # réponse qui oriente vers le SAV
    date : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    rel_conversation = relationship("Conversation", back_populates="rel_message")

    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="ck_message_role"),)
