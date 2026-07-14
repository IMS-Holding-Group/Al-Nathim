import re
import sqlite3
import unicodedata
from datetime import datetime

from config import DATABASE_PATH, REGULATIONS_DIR

MAX_CHUNK_LENGTH = 1200

STOP_WORDS = {
    "من", "في", "على", "إلى", "الى", "عن", "ما", "هل", "كيف", "متى",
    "لماذا", "أين", "اين", "هذا", "هذه", "ذلك", "تلك", "التي", "الذي",
    "اللذان", "اللتان", "الذين", "اللاتي", "اللواتي", "إن", "ان", "أن",
    "او", "أو", "ثم", "قد", "لم", "لن", "لا", "مع", "بين", "عند", "بعد",
    "قبل", "كل", "بعض", "أي", "اي", "هو", "هي", "هم", "هن", "أنا", "انا",
    "نحن", "أنت", "انت", "أنتم", "انتم", "كان", "كانت", "يكون", "تكون",
    "و", "ف", "ب", "ك", "ل", "يا", "إذا", "اذا", "حتى", "إلا", "الا",
    "أيضا", "ايضا", "فقط", "حول", "خلال", "ضمن", "فوق", "تحت", "هناك",
    "هنا", "ماذا", "بماذا", "كم", "مثل", "غير", "سوى", "بل", "لكن",
    "لأن", "لان", "لكي", "حيث", "منذ", "عبر", "إليه", "اليه", "عليه",
    "فيها", "منه", "منها", "بهم", "بهم", "لي", "لك", "له", "لها",
}

REGULATION_FILES = [
    {
        "filename": "laeha_derasah_wa_ekhtebarat.md",
        "regulation_name": "لائحة الدراسة والاختبارات",
    },
    {
        "filename": "daleel_al_taleb_al_akademi.md",
        "regulation_name": "دليل الطالب الأكاديمي (مسيرتي)",
    },
]


def get_connection():
    # إنشاء مجلد قاعدة البيانات إن لم يكن موجودًا
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    # إنشاء الجداول وتحميل اللوائح الرسمية عند أول تشغيل
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS regulation_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_text TEXT NOT NULL,
            regulation_name TEXT NOT NULL,
            article_number TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qa_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            source_regulation TEXT,
            source_article TEXT,
            source_chunk TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)

    cursor.execute("SELECT COUNT(*) AS total FROM regulation_chunks")
    if cursor.fetchone()["total"] == 0:
        load_regulation_files(cursor)

    conn.commit()
    conn.close()


def normalize_arabic(text):
    # تطبيع النص العربي للمقارنة: توحيد الحروف وإزالة التشكيل والمسافات الزائدة
    if not text:
        return ""

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه").replace("ى", "ي")
    text = text.replace("ؤ", "و").replace("ئ", "ي")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def extract_keywords(text):
    # استخراج الكلمات الدلالية بعد التطبيع واستبعاد الكلمات الشائعة
    normalized = normalize_arabic(text)
    words = []
    seen = set()

    for word in normalized.split():
        if len(word) < 2:
            continue
        if word in STOP_WORDS:
            continue
        if word in seen:
            continue
        seen.add(word)
        words.append(word)

    return words


def split_long_text(text, max_length=MAX_CHUNK_LENGTH):
    # تقسيم النص الطويل إلى مقاطع فرعية دون قطع الجملة في منتصفها
    text = text.strip()
    if len(text) <= max_length:
        return [text] if text else []

    sentences = re.split(r"(?<=[.!؟\n])\s+", text)
    parts = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > max_length:
            if current:
                parts.append(current.strip())
                current = ""
            for i in range(0, len(sentence), max_length):
                parts.append(sentence[i:i + max_length].strip())
            continue

        candidate = (current + " " + sentence).strip() if current else sentence
        if len(candidate) <= max_length:
            current = candidate
        else:
            if current:
                parts.append(current.strip())
            current = sentence

    if current:
        parts.append(current.strip())

    return [part for part in parts if part]


def parse_markdown_chunks(content, regulation_name):
    # تقسيم الملف حسب عناوين ## و ### مع حفظ أقرب عنوان لكل مقطع
    lines = content.splitlines()
    chunks = []
    current_heading = regulation_name
    current_lines = []

    def flush_section():
        nonlocal current_lines
        body = "\n".join(current_lines).strip()
        current_lines = []
        if not body:
            return

        for part in split_long_text(body):
            chunks.append({
                "chunk_text": part,
                "regulation_name": regulation_name,
                "article_number": current_heading,
            })

    for line in lines:
        heading_match = re.match(r"^(#{2,3})\s+(.+)$", line.strip())
        if heading_match:
            flush_section()
            current_heading = heading_match.group(2).strip()
            continue

        if line.strip().startswith("# ") and not line.strip().startswith("##"):
            continue

        current_lines.append(line)

    flush_section()
    return chunks


def load_regulation_files(cursor):
    # قراءة ملفات اللوائح الرسمية وتقسيمها إلى مقاطع ثم إدخالها في القاعدة
    all_chunks = []

    for item in REGULATION_FILES:
        file_path = REGULATIONS_DIR / item["filename"]
        if not file_path.exists():
            print(f"ملف اللائحة غير موجود: {file_path}")
            continue

        content = file_path.read_text(encoding="utf-8")
        chunks = parse_markdown_chunks(content, item["regulation_name"])
        all_chunks.extend(chunks)
        print(f"تم تحميل {len(chunks)} مقطعًا من: {item['regulation_name']}")

    if not all_chunks:
        print("لم يتم العثور على مقاطع لتحميلها من ملفات اللوائح.")
        return

    rows = [
        (chunk["chunk_text"], chunk["regulation_name"], chunk["article_number"])
        for chunk in all_chunks
    ]

    cursor.executemany(
        """
        INSERT INTO regulation_chunks (chunk_text, regulation_name, article_number)
        VALUES (?, ?, ?)
        """,
        rows,
    )
    print(f"إجمالي المقاطع المُدخلة في قاعدة البيانات: {len(rows)}")


def search_regulation_chunks(question):
    # بحث نصي محسّن مع تطبيع عربي وحساب درجات التطابق
    keywords = extract_keywords(question)
    if not keywords:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, chunk_text, regulation_name, article_number FROM regulation_chunks"
    )
    rows = cursor.fetchall()
    conn.close()

    best_match = None
    best_score = 0
    best_length = 0

    for row in rows:
        chunk_text = row["chunk_text"]
        regulation_name = row["regulation_name"]
        article_number = row["article_number"]

        norm_text = normalize_arabic(chunk_text)
        norm_title = normalize_arabic(f"{regulation_name} {article_number}")

        score = 0
        matched_words = 0

        for word in keywords:
            found_in_text = word in norm_text
            found_in_title = word in norm_title

            if found_in_text:
                score += 2
            if found_in_title:
                score += 1
            if found_in_text or found_in_title:
                matched_words += 1

        # مكافأة بسيطة عند تطابق أكثر من كلمة دلالية مختلفة
        if matched_words > 1:
            score += matched_words

        text_length = len(chunk_text)

        if score > best_score:
            best_score = score
            best_match = dict(row)
            best_length = text_length
        elif score == best_score and score > 0:
            # عند تساوي الدرجة يُفضَّل المقطع الأنسب طولًا (أقرب إلى 400–900 حرف)
            ideal = 650
            current_distance = abs(text_length - ideal)
            best_distance = abs(best_length - ideal)
            if current_distance < best_distance:
                best_match = dict(row)
                best_length = text_length

    if best_score == 0:
        return None

    return best_match


def save_qa_log(question, answer):
    # حفظ السؤال والإجابة في السجل العام
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        INSERT INTO qa_log (question, answer, created_at)
        VALUES (?, ?, ?)
        """,
        (question, answer, created_at),
    )

    conn.commit()
    conn.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_user(full_name, email, password_hash):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (full_name, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (full_name, email.lower().strip(), password_hash, _now()),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_name, email, password_hash, created_at FROM users WHERE email = ?",
        (email.lower().strip(),),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_conversation(user_id, title):
    conn = get_connection()
    cursor = conn.cursor()
    stamp = _now()
    safe_title = title.strip()[:80] if title.strip() else "محادثة جديدة"
    cursor.execute(
        """
        INSERT INTO conversations (user_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, safe_title, stamp, stamp),
    )
    conversation_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return conversation_id


def get_user_conversations(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (user_id,),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_conversation_for_user(conversation_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, user_id, title, created_at, updated_at
        FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (conversation_id, user_id),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_conversation_messages(conversation_id, user_id):
    conversation = get_conversation_for_user(conversation_id, user_id)
    if not conversation:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, role, content, source_regulation, source_article, source_chunk, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        """,
        (conversation_id,),
    )
    messages = []
    for row in cursor.fetchall():
        item = dict(row)
        source = None
        if item["source_regulation"]:
            source = {
                "regulation_name": item["source_regulation"],
                "article_number": item["source_article"] or "",
                "chunk_text": item["source_chunk"] or "",
            }
        messages.append({
            "id": item["id"],
            "role": item["role"],
            "content": item["content"],
            "source": source,
            "created_at": item["created_at"],
        })
    conn.close()
    return {"conversation": conversation, "messages": messages}


def add_message(conversation_id, role, content, source=None):
    conn = get_connection()
    cursor = conn.cursor()
    stamp = _now()
    source_regulation = None
    source_article = None
    source_chunk = None
    if source:
        source_regulation = source.get("regulation_name")
        source_article = source.get("article_number")
        source_chunk = source.get("chunk_text")

    cursor.execute(
        """
        INSERT INTO messages (
            conversation_id, role, content,
            source_regulation, source_article, source_chunk, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            role,
            content,
            source_regulation,
            source_article,
            source_chunk,
            stamp,
        ),
    )
    cursor.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (stamp, conversation_id),
    )
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return message_id


def delete_conversation(conversation_id, user_id):
    conversation = get_conversation_for_user(conversation_id, user_id)
    if not conversation:
        return False

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    cursor.execute(
        "DELETE FROM conversations WHERE id = ? AND user_id = ?",
        (conversation_id, user_id),
    )
    conn.commit()
    conn.close()
    return True


def rename_conversation(conversation_id, user_id, title):
    conversation = get_conversation_for_user(conversation_id, user_id)
    if not conversation:
        return False

    safe_title = title.strip()[:80]
    if not safe_title:
        return False

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (safe_title, _now(), conversation_id, user_id),
    )
    conn.commit()
    conn.close()
    return True
