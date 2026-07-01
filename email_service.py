import os
import urllib.request
import urllib.error
import json

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
APP_URL = os.environ.get("APP_URL", "http://localhost:8000")
FROM_EMAIL = "YDS Mentor AI <onboarding@resend.dev>"


def _send_email(to_email: str, subject: str, html: str) -> bool:
    """Resend API'ye istek atarak email gönderir. Başarılıysa True döner."""
    if not RESEND_API_KEY:
        print("[EMAIL] RESEND_API_KEY ayarlanmamış, email gönderilmedi.")
        return False

    payload = json.dumps({
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status in (200, 201)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[EMAIL] Resend hatası {e.code}: {body}")
        return False
    except Exception as e:
        print(f"[EMAIL] Beklenmeyen hata: {e}")
        return False


def send_verification_email(to_email: str, token: str) -> bool:
    link = f"{APP_URL}/verify-email?token={token}"
    html = f"""
    <div style="font-family:Inter,sans-serif;max-width:500px;margin:0 auto;background:#0b0f19;color:#f8fafc;padding:40px;border-radius:16px;">
        <h1 style="color:#38bdf8;font-size:24px;margin-bottom:8px;">🎓 YDS Mentor AI</h1>
        <h2 style="font-size:18px;font-weight:600;margin-bottom:16px;">Email Adresini Doğrula</h2>
        <p style="color:#94a3b8;line-height:1.7;margin-bottom:24px;">
            Hesabını aktif etmek için aşağıdaki butona tıkla. Bu link <strong>1 saat</strong> geçerlidir.
        </p>
        <a href="{link}" style="display:inline-block;background:#38bdf8;color:#0f172a;padding:14px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;">
            ✅ Email Adresimi Doğrula
        </a>
        <p style="color:#475569;font-size:12px;margin-top:24px;">
            Bu emaili sen istemediysen görmezden gelebilirsin.
        </p>
    </div>
    """
    return _send_email(to_email, "YDS Mentor AI — Email Doğrulama", html)


def send_password_reset_email(to_email: str, token: str) -> bool:
    link = f"{APP_URL}/reset-password?token={token}"
    html = f"""
    <div style="font-family:Inter,sans-serif;max-width:500px;margin:0 auto;background:#0b0f19;color:#f8fafc;padding:40px;border-radius:16px;">
        <h1 style="color:#38bdf8;font-size:24px;margin-bottom:8px;">🎓 YDS Mentor AI</h1>
        <h2 style="font-size:18px;font-weight:600;margin-bottom:16px;">Şifre Sıfırlama</h2>
        <p style="color:#94a3b8;line-height:1.7;margin-bottom:24px;">
            Şifre sıfırlama isteği aldık. Aşağıdaki butona tıklayarak yeni şifreni belirleyebilirsin. Bu link <strong>1 saat</strong> geçerlidir.
        </p>
        <a href="{link}" style="display:inline-block;background:#38bdf8;color:#0f172a;padding:14px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;">
            🔑 Yeni Şifre Belirle
        </a>
        <p style="color:#475569;font-size:12px;margin-top:24px;">
            Bu isteği sen yapmadıysan şifreni değiştirmene gerek yok.
        </p>
    </div>
    """
    return _send_email(to_email, "YDS Mentor AI — Şifre Sıfırlama", html)
