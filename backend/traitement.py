from docling.document_converter import DocumentConverter

def traitement_docx( file ):
    convertisseur = DocumentConverter()
    fichier = convertisseur.convert(file).document
    return fichier


    