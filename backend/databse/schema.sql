-- ============================================================
--  Base electrodomus - schema
--  PostgreSQL 16 + pgvector
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

create table Modele (
Modele varchar(50) primary key,
type varchar(150)
);

create table Erreur (
Code_erreur varchar(20) NOT NULL,
Modele varchar(50) references Modele(Modele) NOT NULL,
signification varchar(150) not null,
conduite varchar(255) not null,
intervention varchar(255) not null,
PRIMARY KEY (Modele, Code_erreur)
);

create table document (
IDdocument serial primary key,
Titre varchar(150) NOT NULL,
Contenu text not null,
Modele varchar(50) references Modele(Modele) NULL,
Date_enr timestamptz default now()
);

create table Chunk (
IDchunk serial primary key,
IDdocument int references document(IDdocument),
Modele varchar(50) references Modele(Modele),
Code_erreur varchar(20),
Chunk text not null,
vecteur vector(1536),          -- dimension a adapter au modele d'embedding
FOREIGN KEY (Modele, Code_erreur) REFERENCES Erreur(Modele, Code_erreur)
);