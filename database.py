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
    """Veritabanını ve tabloyu oluşturur (yoksa)."""
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


def get_question_count(category):
    """Belirtilen kategoride kaç soru olduğunu döndürür."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ai_questions WHERE category = %s", (category,))
        return cursor.fetchone()[0]
    finally:
        conn.close()
