import os
from pathlib import Path

from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env في جذر المشروع
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# مسار قاعدة بيانات SQLite
DATABASE_PATH = BASE_DIR / "database" / "db.sqlite3"

# مجلد ملفات اللوائح الرسمية
REGULATIONS_DIR = BASE_DIR / "data" / "regulations"

# مفاتيح واجهات الذكاء الاصطناعي
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# المزوّد المفضل: openrouter (افتراضي) أو gemini
AI_PROVIDER = os.getenv("AI_PROVIDER", "openrouter").lower()

# نموذج Gemini المستخدم كبديل اختياري
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# نموذج OpenRouter الأساسي (مسار مجاني تلقائي عند توفره)
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

# معرّف المشروع في رؤوس طلبات OpenRouter
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost:5000")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Al-Nathim")

# مفتاح جلسات Flask
SECRET_KEY = os.getenv("SECRET_KEY", "al-nathim-dev-secret-change-me")
