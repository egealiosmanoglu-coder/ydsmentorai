from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from database import (
    init_db,
    save_ai_question,
    get_random_stored_question,
    get_question_by_id,
    get_question_count,
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user_stats,
)
from models import (
    DiagnosticTestSubmission,
    DiagnosticResult,
    AIQuestionFormat,
    UserRegister,
    UserLogin,
    UserOut,
    TokenResponse,
    AnswerSubmission,
)
from auth import hash_password, verify_password, create_token, get_current_user_id

from fastapi import Depends

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


@app.post("/api/register", response_model=TokenResponse)
def register(payload: UserRegister):
    email = payload.email.strip().lower()
    if "@" not in email or len(payload.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Geçerli bir email ve en az 6 karakterli bir şifre girmelisin.",
        )

    user_id = create_user(email, hash_password(payload.password))
    if user_id is None:
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı.")

    token = create_token(user_id)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user_id, email=email, solved_count=0, correct_count=0),
    )


@app.post("/api/login", response_model=TokenResponse)
def login(payload: UserLogin):
    email = payload.email.strip().lower()
    row = get_user_by_email(email)
    if not row or not verify_password(payload.password, row[2]):
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı.")

    user_id, user_email, _hash, solved_count, correct_count = row
    token = create_token(user_id)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user_id, email=user_email, solved_count=solved_count, correct_count=correct_count),
    )


@app.get("/api/me", response_model=UserOut)
def get_me(user_id: int = Depends(get_current_user_id)):
    row = get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    uid, email, _hash, solved_count, correct_count = row
    return UserOut(id=uid, email=email, solved_count=solved_count, correct_count=correct_count)


@app.post("/api/answer", response_model=UserOut)
def answer_question(payload: AnswerSubmission, user_id: int = Depends(get_current_user_id)):
    """
    Frontend cevabın doğru olup olmadığını zaten bildiği için (soru içinde
    correct_option var), is_correct bilgisini de bu endpoint'e gönderir.
    İstatistik veritabanında, kullanıcıya özel olarak güncellenir.
    """
    row = get_question_by_id(payload.question_id)
    correct_option = row[3] if row else None

    is_correct = (correct_option is not None) and (payload.selected_option == correct_option)
    update_user_stats(user_id, is_correct)

    urow = get_user_by_id(user_id)
    uid, email, _hash, solved_count, correct_count = urow
    return UserOut(id=uid, email=email, solved_count=solved_count, correct_count=correct_count)



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
