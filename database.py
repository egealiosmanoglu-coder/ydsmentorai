import os
import json
import secrets
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL ortam değişkeni ayarlanmamış.")
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_questions (
                id SERIAL PRIMARY KEY,
                category TEXT NOT NULL,
                question_text TEXT NOT NULL,
                options TEXT NOT NULL,
                correct_option TEXT NOT NULL,
                ai_explanation TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                solved_count INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                token TEXT UNIQUE NOT NULL,
                token_type TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Eski users tablosunda is_verified yoksa ekle
        cursor.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE
        """)
        conn.commit()
    finally:
        conn.close()


# ── Kullanıcı işlemleri ──────────────────────────────────────────────────────

def create_user(email, password_hash):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (email, password_hash, is_verified)
                VALUES (%s, %s, FALSE) RETURNING id
            """, (email, password_hash))
            user_id = cursor.fetchone()[0]
            conn.commit()
            return user_id
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return None
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email, password_hash, solved_count, correct_count, is_verified
            FROM users WHERE email = %s
        """, (email,))
        return cursor.fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email, password_hash, solved_count, correct_count, is_verified
            FROM users WHERE id = %s
        """, (user_id,))
        return cursor.fetchone()
    finally:
        conn.close()


def verify_user_email(user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_verified = TRUE WHERE id = %s", (user_id,))
        conn.commit()
    finally:
        conn.close()


def update_user_stats(user_id, is_correct):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if is_correct:
            cursor.execute("""
                UPDATE users SET solved_count = solved_count + 1, correct_count = correct_count + 1
                WHERE id = %s
            """, (user_id,))
        else:
            cursor.execute("UPDATE users SET solved_count = solved_count + 1 WHERE id = %s", (user_id,))
        conn.commit()
    finally:
        conn.close()


def update_user_password(user_id, new_password_hash):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_password_hash, user_id))
        conn.commit()
    finally:
        conn.close()


def get_all_users():
    """Admin paneli için tüm kullanıcıları döndürür."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email, is_verified, solved_count, correct_count, created_at
            FROM users ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()


# ── Token işlemleri ──────────────────────────────────────────────────────────

def create_email_token(user_id, token_type, expires_minutes=60):
    """Doğrulama veya şifre sıfırlama tokeni oluşturur."""
    import datetime
    token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=expires_minutes)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Aynı kullanıcı için eski tokenleri geçersiz kıl
        cursor.execute("""
            UPDATE email_tokens SET used = TRUE
            WHERE user_id = %s AND token_type = %s AND used = FALSE
        """, (user_id, token_type))
        cursor.execute("""
            INSERT INTO email_tokens (user_id, token, token_type, expires_at)
            VALUES (%s, %s, %s, %s)
        """, (user_id, token, token_type, expires_at))
        conn.commit()
        return token
    finally:
        conn.close()


def use_email_token(token, token_type):
    """
    Tokeni doğrular ve kullanılmış olarak işaretler.
    Geçerliyse user_id döner, değilse None.
    """
    import datetime
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, expires_at, used FROM email_tokens
            WHERE token = %s AND token_type = %s
        """, (token, token_type))
        row = cursor.fetchone()
        if not row:
            return None
        token_id, user_id, expires_at, used = row
        if used or expires_at < datetime.datetime.utcnow():
            return None
        cursor.execute("UPDATE email_tokens SET used = TRUE WHERE id = %s", (token_id,))
        conn.commit()
        return user_id
    finally:
        conn.close()


# ── Soru işlemleri ───────────────────────────────────────────────────────────

def save_ai_question(category, question_text, options, correct_option, ai_explanation):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_questions (category, question_text, options, correct_option, ai_explanation)
            VALUES (%s, %s, %s, %s, %s)
        """, (category, question_text, json.dumps(options, ensure_ascii=False), correct_option, ai_explanation))
        conn.commit()
    finally:
        conn.close()


def get_random_stored_question(category):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, question_text, options, correct_option, ai_explanation
            FROM ai_questions WHERE category = %s ORDER BY RANDOM() LIMIT 1
        """, (category,))
        return cursor.fetchone()
    finally:
        conn.close()


def get_question_by_id(question_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, question_text, options, correct_option, ai_explanation
            FROM ai_questions WHERE id = %s
        """, (question_id,))
        return cursor.fetchone()
    finally:
        conn.close()


def question_exists(question_text):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM ai_questions WHERE question_text = %s LIMIT 1", (question_text,))
        return cursor.fetchone() is not None
    finally:
        conn.close()


def get_question_count(category):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ai_questions WHERE category = %s", (category,))
        return cursor.fetchone()[0]
    finally:
        conn.close()
