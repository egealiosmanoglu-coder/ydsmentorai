import os
import json
import psycopg2

# Neon (veya başka bir Postgres sağlayıcısı) bağlantı adresi, Render'da
# environment variable olarak ayarlanacak. Örnek format:
# postgresql://kullanici:sifre@host/dbisim?sslmode=require
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL ortam değişkeni ayarlanmamış. "
            "Render'da Environment sekmesinden Neon bağlantı adresini eklemelisin."
        )
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """Veritabanını ve tabloları oluşturur (yoksa)."""
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
                created_at TIMESTAMP DEFAULT NOW(),
                solved_count INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()
    finally:
        conn.close()


def create_user(email, password_hash):
    """Yeni bir kullanıcı oluşturur, id'sini döndürür. Email zaten varsa None döner."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id
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
    """Email ile kullanıcıyı döndürür: (id, email, password_hash, solved_count, correct_count) veya None."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email, password_hash, solved_count, correct_count
            FROM users WHERE email = %s
        """, (email,))
        return cursor.fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    """ID ile kullanıcıyı döndürür."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email, password_hash, solved_count, correct_count
            FROM users WHERE id = %s
        """, (user_id,))
        return cursor.fetchone()
    finally:
        conn.close()


def update_user_stats(user_id, is_correct):
    """Kullanıcının çözdüğü/doğru sayısını bir artırır."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if is_correct:
            cursor.execute("""
                UPDATE users SET solved_count = solved_count + 1, correct_count = correct_count + 1
                WHERE id = %s
            """, (user_id,))
        else:
            cursor.execute("""
                UPDATE users SET solved_count = solved_count + 1
                WHERE id = %s
            """, (user_id,))
        conn.commit()
    finally:
        conn.close()


def save_ai_question(category, question_text, options, correct_option, ai_explanation):
    """Yeni bir soruyu veritabanına kaydeder. Türkçe karakterler korunur (ensure_ascii=False)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_questions (category, question_text, options, correct_option, ai_explanation)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            category,
            question_text,
            json.dumps(options, ensure_ascii=False),
            correct_option,
            ai_explanation,
        ))
        conn.commit()
    finally:
        conn.close()


def get_random_stored_question(category):
    """Belirtilen kategoriden rastgele bir soru döndürür."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, question_text, options, correct_option, ai_explanation
            FROM ai_questions
            WHERE category = %s
            ORDER BY RANDOM() LIMIT 1
        """, (category,))
        return cursor.fetchone()
    finally:
        conn.close()


def get_question_by_id(question_id):
    """Belirtilen id'ye sahip soruyu döndürür."""
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


def get_question_count(category):
    """Belirtilen kategoride kaç soru olduğunu döndürür."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ai_questions WHERE category = %s", (category,))
        return cursor.fetchone()[0]
    finally:
        conn.close()
