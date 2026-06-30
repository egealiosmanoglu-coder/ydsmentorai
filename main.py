from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from database import (
    init_db,
    save_ai_question,
    get_random_stored_question,
    get_question_count,
)
from models import DiagnosticTestSubmission, DiagnosticResult, AIQuestionFormat

import json

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

# Uygulama ilk açıldığında depo boşsa eklenecek örnek sorular.
# Gerçek kullanımda burayı, bir arka plan görevinin (örn. bir LLM API'sine
# soru üretme isteği gönderen bir worker) doldurduğu sorularla
# değiştirebilir veya /api/add-question endpoint'ini kullanabilirsin.
SEED_QUESTIONS = [
    {
        "question_text": "The government decided to ------- the old building because it was no longer safe for public use.",
        "options": {"A": "demolish", "B": "construct", "C": "renovate", "D": "preserve", "E": "abandon"},
        "correct_option": "A",
        "ai_explanation": "Cümlede binanın artık güvenli olmadığı (no longer safe) belirtilerek yıkılması kararı vurgulanmıştır. 'Demolish' (yıkmak, yerle bir etmek) kelimesi bağlama tam uymaktadır.",
    },
    {
        "question_text": "Despite the heavy criticism, the committee remained ------- in its decision to approve the new policy.",
        "options": {"A": "hesitant", "B": "resolute", "C": "ambiguous", "D": "indifferent", "E": "reluctant"},
        "correct_option": "B",
        "ai_explanation": "'Despite' kelimesi bir zıtlık kurar: eleştirilere rağmen komite kararından vazgeçmemiştir. 'Resolute' (kararlı, azimli) bu zıtlığa en uygun anlamı verir.",
    },
    {
        "question_text": "The scientist's findings were so ------- that even her harshest critics had to acknowledge their validity.",
        "options": {"A": "trivial", "B": "compelling", "C": "questionable", "D": "obscure", "E": "premature"},
        "correct_option": "B",
        "ai_explanation": "Cümlede en sert eleştirmenlerin bile bulguların geçerliliğini kabul etmek zorunda kaldığı belirtiliyor; bu da bulguların ikna edici/güçlü olduğunu gösterir. 'Compelling' (ikna edici, etkileyici) doğru seçenektir.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if get_question_count("vocabulary") == 0:
        for q in SEED_QUESTIONS:
            save_ai_question(
                category="vocabulary",
                question_text=q["question_text"],
                options=q["options"],
                correct_option=q["correct_option"],
                ai_explanation=q["ai_explanation"],
            )
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/next-question")
def next_question():
    category = "vocabulary"
    count = get_question_count(category)

    if count == 0:
        return {"error": "loading"}

    row = get_random_stored_question(category)
    if not row:
        return {"error": "loading"}

    return {
        "id": row[0],
        "question_text": row[1],
        "options": json.loads(row[2]),
        "correct_option": row[3],
        "ai_explanation": row[4],
        "current_count": count,
    }


@app.post("/api/add-question")
def add_question(payload: AIQuestionFormat):
    """
    Yeni bir soruyu depoya ekler. Bu endpoint, soruları otomatik üreten
    bir dış servis (örn. bir LLM'e istek atan bir script) tarafından
    çağrılmak üzere tasarlanmıştır; ai_explanation alanını da
    payload'a eklemen gerekirse modeli genişletebilirsin.
    """
    if payload.correct_option not in payload.options:
        raise HTTPException(status_code=400, detail="correct_option, options içinde bulunmalı.")

    save_ai_question(
        category=payload.category,
        question_text=payload.question_text,
        options=payload.options,
        correct_option=payload.correct_option,
        ai_explanation="",
    )
    return {"status": "ok", "current_count": get_question_count(payload.category)}


@app.get("/", response_class=HTMLResponse)
def read_index():
    if not INDEX_FILE.exists():
        return HTMLResponse(
            "🌀 Hata: 'index.html' dosyası bulunamadı! "
            "Lütfen main.py ile aynı klasörde olduğundan emin ol.",
            status_code=500,
        )
    return INDEX_FILE.read_text(encoding="utf-8")
