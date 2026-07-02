import os
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

import google.generativeai as genai

from database import (
    init_db,
    save_ai_question,
    get_random_stored_question,
    get_question_by_id,
    get_question_count,
    question_exists,
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user_stats,
    verify_user_email,
    update_user_password,
    create_email_token,
    use_email_token,
    get_all_users,
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
    AskMentorRequest,
)
from auth import hash_password, verify_password, create_token, get_current_user_id
from email_service import send_verification_email, send_password_reset_email

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

# Çevresel Değişkenler
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "degistir-bunu")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Gemini API Yapılandırması
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


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
    {
        "question_text": "The negotiations were ------- by both parties' refusal to make even the smallest compromise.",
        "options": {"A": "facilitated", "B": "hindered", "C": "accelerated", "D": "celebrated", "E": "simplified"},
        "correct_option": "B",
        "ai_explanation": "Her iki tarafın da küçük bir tavizden bile kaçınması müzakerelerin önünü tıkamıştır. 'Hindered' (engellenmiş, aksamış) bu olumsuz etkiyi karşılar.",
    },
    {
        "question_text": "Although the evidence was largely -------, the jury still found it convincing enough to reach a verdict.",
        "options": {"A": "circumstantial", "B": "conclusive", "C": "irrelevant", "D": "fabricated", "E": "redundant"},
        "correct_option": "A",
        "ai_explanation": "'Although' zıtlık kurar: kanıt dolaylı/kesin olmamasına rağmen jüri yine de ikna olmuştur. 'Circumstantial' (dolaylı, ipuçlarına dayanan) bu zıtlığa uyar.",
    },
    {
        "question_text": "The company's profits have shown a ------- decline over the past three quarters, raising concerns among investors.",
        "options": {"A": "negligible", "B": "marginal", "C": "steady", "D": "momentary", "E": "reversible"},
        "correct_option": "C",
        "ai_explanation": "Üç çeyrek boyunca süren ve yatırımcıları endişelendiren bir düşüş, ani değil sürekli/istikrarlı bir gerilemeyi işaret eder. 'Steady' (istikrarlı, sürekli) doğru seçenektir.",
    },
    {
        "question_text": "Her ------- to detail made her the perfect candidate for the meticulous research position.",
        "options": {"A": "indifference", "B": "attention", "C": "aversion", "D": "resistance", "E": "neglect"},
        "correct_option": "B",
        "ai_explanation": "Titiz bir araştırma pozisyonu için ideal aday olmasının sebebi detaylara verdiği önemdir. 'Attention to detail' (detaylara dikkat) kalıbı bağlama uyar.",
    },
    {
        "question_text": "The new regulations are intended to ------- pollution levels in urban areas over the next decade.",
        "options": {"A": "exacerbate", "B": "mitigate", "C": "ignore", "D": "publicize", "E": "complicate"},
        "correct_option": "B",
        "ai_explanation": "Yeni düzenlemelerin amacı kirliliği azaltmaktır. 'Mitigate' (hafifletmek, azaltmak) bu olumlu amaca uygun düşer.",
    },
    {
        "question_text": "The professor's lecture was so ------- that several students struggled to follow the main argument.",
        "options": {"A": "lucid", "B": "convoluted", "C": "concise", "D": "engaging", "E": "rehearsed"},
        "correct_option": "B",
        "ai_explanation": "Öğrencilerin ana fikri takip etmekte zorlanması dersin karmaşık/dolambaçlı olduğunu gösterir. 'Convoluted' (karma
