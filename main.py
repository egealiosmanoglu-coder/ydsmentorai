import os
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse

# Yeni ve güncel Google GenAI SDK entegrasyonu
from google import genai
from google.genai import types

from database import (
    init_db,
    save_ai_question,
    get_unsolved_random_question,
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
    log_user_solved_question,
)
from models import (
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

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "degistir-bunu-admin-123")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Yeni SDK istemci başlatma
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"[GEMINI INIT ERROR]: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    
    questions_file = BASE_DIR / "questions.json"
    
    if questions_file.exists():
        with open(questions_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for category, questions in data.items():
            for q in questions:
                if not question_exists(q["question_text"]):
                    save_ai_question(
                        category=category,
                        question_text=q["question_text"],
                        options=q["options"],
                        correct_option=q["correct_option"],
                        ai_explanation=q.get("ai_explanation", ""),
                    )
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/api/register", response_model=TokenResponse)
def register(payload: UserRegister):
    email = payload.email.strip().lower()
    if "@" not in email or len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Geçerli bir email ve en az 6 karakterli bir şifre girmelisin.")

    user_id = create_user(email, hash_password(payload.password))
    if user_id is None:
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı.")

    # Email servisi devre dışı / göz ardı edilebilir olduğu için sessizce çalıştırılır
    try:
        token = create_email_token(user_id, "verify", expires_minutes=60)
        send_verification_email(email, token)
    except Exception as e:
        print(f"[REGISTER EMAIL ERROR]: {e}")

    jwt = create_token(user_id)
    return TokenResponse(
        access_token=jwt,
        user=UserOut(id=user_id, email=email, solved_count=0, correct_count=0, is_verified=True),
    )


@app.post("/api/login", response_model=TokenResponse)
def login(payload: UserLogin):
    email = payload.email.strip().lower()
    row = get_user_by_email(email)
    if not row or not verify_password(payload.password, row[2]):
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı.")

    user_id, user_email, _hash, solved_count, correct_count, is_verified = row
    token = create_token(user_id)
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user_id, email=user_email, solved_count=solved_count, correct_count=correct_count, is_verified=True),
    )


@app.get("/api/me", response_model=UserOut)
def get_me(user_id: int = Depends(get_current_user_id)):
    row = get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    uid, email, _hash, solved_count, correct_count, is_verified = row
    return UserOut(id=uid, email=email, solved_count=solved_count, correct_count=correct_count, is_verified=True)


@app.get("/api/resend-verification")
def resend_verification(user_id: int = Depends(get_current_user_id)):
    row = get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    uid, email, _hash, solved_count, correct_count, is_verified = row
    try:
        token = create_email_token(uid, "verify", expires_minutes=60)
        send_verification_email(email, token)
    except Exception as e:
        print(f"[RESEND EMAIL ERROR]: {e}")
    return {"message": "Doğrulama işlemi simüle edildi veya gönderildi."}


@app.get("/verify-email", response_class=HTMLResponse)
def verify_email(token: str):
    user_id = use_email_token(token, "verify")
    if not user_id:
        return HTMLResponse("""
        <html><body style="font-family:Inter,sans-serif;background:#0b0f19;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;">
        <div style="text-align:center;">
            <div style="font-size:48px;">❌</div>
            <h2 style="color:#f87171;">Geçersiz veya süresi dolmuş link</h2>
            <p style="color:#94a3b8;">Lütfen tekrar doğrulama emaili isteyin.</p>
            <a href="/" style="color:#38bdf8;">← Ana sayfaya dön</a>
        </div></body></html>
        """, status_code=400)
    verify_user_email(user_id)
    return HTMLResponse("""
    <html><body style="font-family:Inter,sans-serif;background:#0b0f19;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;">
    <div style="text-align:center;">
        <div style="font-size:48px;">✅</div>
        <h2 style="color:#34d399;">Email adresin doğrulandı!</h2>
        <p style="color:#94a3b8;">Artık YDS Mentor AI'ı tam olarak kullanabilirsin.</p>
        <a href="/" style="display:inline-block;margin-top:20px;background:#38bdf8;color:#0f172a;padding:12px 24px;border-radius:10px;text-decoration:none;font-weight:700;">
            Uygulamaya Git →
        </a>
    </div></body></html>
    """)


@app.post("/api/forgot-password")
def forgot_password(payload: UserLogin):
    email = payload.email.strip().lower()
    row = get_user_by_email(email)
    if row:
        try:
            token = create_email_token(row[0], "reset", expires_minutes=60)
            send_password_reset_email(email, token)
        except Exception as e:
            print(f"[FORGOT PW EMAIL ERROR]: {e}")
    return {"message": "Kayıtlı bir hesap varsa şifre sıfırlama emaili gönderildi."}


@app.post("/api/reset-password")
def reset_password(token: str, payload: UserRegister):
    user_id = use_email_token(token, "reset")
    if not user_id:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş link.")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Şifre en az 6 karakter olmalı.")
    update_user_password(user_id, hash_password(payload.password))
    return {"message": "Şifren başarıyla güncellendi. Giriş yapabilirsin."}


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(token: str):
    return HTMLResponse(f"""
    <html><head><title>Şifre Sıfırla - YDS Mentor AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family:Inter,sans-serif;background:#0b0f19;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0; }}
        .card {{ background:rgba(30,41,59,0.4);padding:40px;border-radius:20px;border:1px solid rgba(255,255,255,0.08);width:100%;max-width:360px; }}
        h2 {{ margin-bottom:8px;font-size:20px; }}
        p {{ color:#94a3b8;font-size:13px;margin-bottom:24px; }}
        input {{ width:100%;box-sizing:border-box;padding:12px 14px;margin-bottom:12px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.1);border-radius:10px;color:#f8fafc;font-size:14px;font-family:inherit; }}
        input:focus {{ outline:none;border-color:#38bdf8; }}
        button {{ background:#38bdf8;color:#0f172a;border:none;padding:14px;font-size:15px;font-weight:700;border-radius:10px;cursor:pointer;width:100%; }}
        .msg {{ margin-top:12px;font-size:13px;text-align:center; }}
    </style></head>
    <body><div class="card">
        <h2>🔑 Yeni Şifre Belirle</h2>
        <p>En az 6 karakterli yeni şifreni gir.</p>
        <input type="password" id="pw" placeholder="Yeni şifre">
        <input type="password" id="pw2" placeholder="Şifreyi tekrarla">
        <button onclick="doReset()">Şifremi Güncelle</button>
        <div class="msg" id="msg"></div>
    </div>
    <script>
        async function doReset() {{
            const pw = document.getElementById('pw').value;
            const pw2 = document.getElementById('pw2').value;
            const msg = document.getElementById('msg');
            if (pw !== pw2) {{ msg.style.color='#f87171'; msg.innerText='Şifreler eşleşmiyor.'; return; }}
            if (pw.length < 6) {{ msg.style.color='#f87171'; msg.innerText='En az 6 karakter olmalı.'; return; }}
            const res = await fetch('/api/reset-password?token={token}', {{
                method:'POST', headers:{{'Content-Type':'application/json'}},
                body: JSON.stringify({{email:'placeholder@x.com', password:pw}})
            }});
            const data = await res.json();
            if (res.ok) {{
                msg.style.color='#34d399';
                msg.innerHTML = data.message + ' <a href="/" style="color:#38bdf8;">Giriş yap →</a>';
            }} else {{
                msg.style.color='#f87171'; msg.innerText = data.detail || 'Bir hata oluştu.';
            }}
        }}
    </script></body></html>
    """)


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(secret: str = ""):
    if secret != ADMIN_SECRET:
        return HTMLResponse("<h2 style='font-family:sans-serif;padding:40px;color:red;'>❌ Yetkisiz erişim.</h2>", status_code=403)
    users = get_all_users()
    rows = ""
    for u in users:
        uid, email, is_verified, solved, correct, created_at = u
        ratio = f"{round(correct/solved*100)}%" if solved > 0 else "—"
        verified = "✅" if is_verified else "⏳"
        rows += f"<tr><td>{uid}</td><td>{email}</td><td>{verified}</td><td>{solved}</td><td>{ratio}</td><td>{str(created_at)[:16]}</td></tr>"
    return HTMLResponse(f"""
    <html><head><title>Admin - YDS Mentor AI</title>
    <style>
        body {{ font-family:Inter,sans-serif;background:#0b0f19;color:#f8fafc;padding:40px;margin:0; }}
        h1 {{ color:#38bdf8;margin-bottom:24px; }}
        table {{ width:100%;border-collapse:collapse; }}
        th {{ background:rgba(56,189,248,0.1);padding:12px;text-align:left;font-size:13px;color:#38bdf8;border-bottom:1px solid rgba(255,255,255,0.08); }}
        td {{ padding:12px;font-size:13px;border-bottom:1px solid rgba(255,255,255,0.04); }}
        tr:hover td {{ background:rgba(255,255,255,0.02); }}
    </style></head>
    <body>
        <h1>🛡️ Admin Paneli</h1>
        <p style="color:#64748b;margin-bottom:24px;">Toplam kullanıcı: <strong style="color:#f8fafc">{len(users)}</strong></p>
        <table>
            <tr><th>ID</th><th>Email</th><th>Doğrulandı</th><th>Çözülen</th><th>Başarı</th><th>Kayıt Tarihi</th></tr>
            {rows}
        </table>
    </body></html>
    """)


@app.post("/api/answer", response_model=UserOut)
def answer_question(payload: AnswerSubmission, user_id: int = Depends(get_current_user_id)):
    row = get_question_by_id(payload.question_id)
    correct_option = row[3] if row else None

    is_correct = (correct_option is not None) and (payload.selected_option == correct_option)
    update_user_stats(user_id, is_correct)
    
    log_user_solved_question(user_id, payload.question_id)

    urow = get_user_by_id(user_id)
    uid, email, _hash, solved_count, correct_count, is_verified = urow
    return UserOut(id=uid, email=email, solved_count=solved_count, correct_count=correct_count, is_verified=True)


@app.get("/api/next-question")
def next_question(category: str = "vocabulary", user_id: int = Depends(get_current_user_id)):
    """Kullanıcının seçtiği kategoriye göre dinamik soru getirir."""
    count = get_question_count(category)

    if count == 0:
        return {"error": "loading"}

    row = get_unsolved_random_question(user_id, category)
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


@app.post("/api/ask-mentor")
def ask_mentor(payload: AskMentorRequest, user_id: int = Depends(get_current_user_id)):
    if not client:
        raise HTTPException(status_code=503, detail="Yapay zeka (Gemini API) henüz sisteme bağlanmadı.")

    row = get_question_by_id(payload.question_id)
    if not row:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")
        
    q_id, q_text, q_options, q_correct, q_expl = row

    prompt = f"""
    Sen, YDS ve YÖKDİL sınavlarına hazırlanan öğrencilere yardım eden "YDS Mentor AI" adında uzman, sabırlı, motive edici ve tatlı dilli bir İngilizce öğretmenisin. 
    
    Öğrenci şu an aşağıdaki soruyu çözdü ve senden yardım istiyor:
    - Soru: {q_text}
    - Şıklar: {q_options}
    - Doğru Cevap: {q_correct}

    Öğrencinin sana mesajı: "{payload.user_message}"

    LÜTFEN AŞAĞIDAKİ KURALLARA KESİNLİKLE UY:
    
    1. DURUM ANALİZİ:
       - Sadece tek şık soruluyorsa (Örn: "Neden B?"): O şıkkın anlamına ve boşluğa neden uyup uymadığına odaklan. Bütün şıkları çevirme.
       - "Anlamadım" deniyorsa: Cümlenin temiz bir Türkçe çevirisini ver. Soru kökündeki en büyük ipucunu göster.
       - Konu dışıysa (Matematik, sohbet vs.): Kibarca ve öğretmen tavrıyla, sadece İngilizce testlerinde yardımcı olabileceğini söyle.

    2. YDS TAKTİĞİ VER (Zorunlu):
       - Mümkün olan her açıklamada, öğrenciye o soru tipini daha hızlı çözmesi için minik bir ipucu ver. (Örn: "Boşluktan sonra bir edat (preposition) var, bu yüzden...", veya "Cümle 'Despite' ile başlamış, demek ki eksi (-) bir kelime arıyoruz...").

    3. KELİME DAĞARCIĞI (Synonym Bonusu):
       - Üzerinde konuşulan kelimenin YDS'de en çok çıkan 1 veya 2 eşanlamlısını (synonym) mutlaka parantez içinde belirt.

    4. ETKİLEŞİMİ KORU:
       - Açıklamanı bitirip kestirip atma. Mesajının sonuna her zaman öğrenciyi düşündürecek veya motive edecek minik bir soru ekle.

    ÜSLUP VE FORMAT:
    - Cevapların asla sıkıcı ve boğucu uzunlukta olmasın. Okunması kolay, kısa ve net paragraflar kullan.
    - Emojileri (💡, 📌, 🎯, 🛑) stratejik olarak kullanarak metni görsel olarak çekici hale getir.
    - Vurgulanması gereken önemli kelimeleri ve şıkları **kalın** harflerle yaz.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return {"answer": response.text}
    except Exception as e:
        print(f"[AI ERROR]: {e}")
        raise HTTPException(status_code=500, detail="Yapay zeka şu an meşgul, lütfen birazdan tekrar dene.")


@app.get("/api/ping")
def ping():
    return {"status": "alive"}


@app.get("/", response_class=HTMLResponse)
def read_index():
    if not INDEX_FILE.exists():
        return HTMLResponse(
            "🌀 Hata: 'index.html' dosyası bulunamadı! Lütfen main.py ile aynı klasörde olduğundan emin ol.",
            status_code=500,
        )
    return INDEX_FILE.read_text(encoding="utf-8")
