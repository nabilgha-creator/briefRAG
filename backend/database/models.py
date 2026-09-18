from sqlalchemy.orm import declarative_base , Mapped , mapped_column, relationship
from sqlalchemy import String , Integer ,  ForeignKey , UniqueConstraint, Table, Column, Text, DateTime
from pgvector.sqlalchemy import Vector
from datetime import datetime




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
    type : Mapped[str] = mapped_column(String(150), nullable=True)
    
    rel_erreur = relationship("Erreur", back_populates="rel_modele") 
    rel_chunk_modele = relationship("Chunk" , secondary=chunk_modele, back_populates="rel_chunk_modele")


class Document (Base) : 
    
    __tablename__ = 'document'      
    
    id_document : Mapped[int] = mapped_column(Integer, primary_key=True)
    titre : Mapped[str] = mapped_column(String(150), nullable=False)
    version : Mapped[str] = mapped_column(String(150), nullable=True)
    date_enr : Mapped[datetime] = mapped_column(DateTime(timezone=True) )   
    
    rel_chunk = relationship("Chunk", back_populates="rel_document")
    
class Chunk(Base):
    
    __tablename__ = "chunk"
    
    id_chunk : Mapped[int] = mapped_column(Integer, primary_key=True)
    id_document : Mapped[int] = mapped_column(Integer, ForeignKey("document.id_document", ondelete="CASCADE"), nullable=False)
    position_chunk : Mapped[int] = mapped_column(Integer, nullable=True)
    contenu : Mapped[str] = mapped_column(Text, nullable= False)
    vecteur : Mapped[list[float]] = mapped_column(Vector(1024), nullable=True)
    
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
    
    __table_args__ = UniqueConstraint("modele","code_erreur") 
    