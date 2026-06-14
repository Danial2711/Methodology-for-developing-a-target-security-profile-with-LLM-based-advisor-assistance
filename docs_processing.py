import pdfplumber
import re
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter


def extract_controls_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[27:]:
            text += page.extract_text() + "\n"
    return text


def controls_chunking(input_text):
    documents = []
    ids = []
    metadatas = []
    chunks = re.split(r"(?=[A-ZА-Я]{2}-\d+\s+[А-ЯІЇЄ]{4,})", input_text)[1:-2]

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        match = re.match(
            r"((AC|AT|AU|CA|CM|CP|IA|IR|MA|MP|PE|PL|PM|PS|PT|RA|SA|SC|SI|SR)-\d+)",
            chunk
        )

        if match:
            control_id = match.group(1)
            klas = match.group(2)
            documents.append(chunk)
            ids.append(control_id)
            metadatas.append({
                "control_id": control_id,
                "klas": klas,
                "document_type": "security_control"
            })

    return documents, ids, metadatas


def extract_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text


def docs_chunking(input_text):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=300,
    )

    chunks = splitter.split_text(input_text)

    documents = []
    ids = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        documents.append(chunk)
        ids.append(f"doc_{uuid.uuid4().hex[:8]}_{i}")
        metadatas.append({"document_type": "general_doc"})

    return documents, ids, metadatas