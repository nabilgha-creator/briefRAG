-- ============================================================
--  Base electrodomus - schema
--  PostgreSQL 18+ pgvector
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE modele (
    modele          varchar(50) PRIMARY KEY,
    type            varchar(150)
);

CREATE TABLE erreur (
    id_erreur       serial PRIMARY KEY,
    modele          varchar(50) NOT NULL REFERENCES modele(modele),
    code_erreur     varchar(20) NOT NULL,
    signification   varchar(150) NOT NULL,
    conduite        varchar(255) NOT NULL,
    intervention    varchar(255) NOT NULL,
    UNIQUE (modele, code_erreur)
);

CREATE TABLE document (
    id_document     serial PRIMARY KEY,
    titre           varchar(150) NOT NULL,
    version         varchar(150),
    date_enr        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chunk (
    id_chunk        serial PRIMARY KEY,
    id_document     int NOT NULL REFERENCES document(id_document) ON DELETE CASCADE,
    position_chunk  int,
    contenu         text NOT NULL,
    vecteur         vector(1024)
);

CREATE TABLE chunk_modele (
    id_chunk        int NOT NULL REFERENCES chunk(id_chunk) ON DELETE CASCADE,
    modele          varchar(50) NOT NULL REFERENCES modele(modele),
    PRIMARY KEY (id_chunk, modele)
);

CREATE TABLE chunk_erreur (
    id_chunk        int NOT NULL REFERENCES chunk(id_chunk) ON DELETE CASCADE,
    id_erreur       int NOT NULL REFERENCES erreur(id_erreur) ON DELETE CASCADE,
    PRIMARY KEY (id_chunk, id_erreur)
);