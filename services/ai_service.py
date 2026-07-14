import requests

from config import (
    AI_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME,
    OPENROUTER_MODEL,
    OPENROUTER_SITE_URL,
)


def build_prompt(question, chunk):
    # بناء نص صارم يُلزم النموذج بالإجابة من المقطع فقط بالعربية الفصحى
    regulation_name = chunk["regulation_name"]
    article_number = chunk["article_number"]
    chunk_text = chunk["chunk_text"]

    return (
        "أنت مساعد أكاديمي رسمي باسم «الناظم» في جامعة تبوك.\n"
        "التزم بالقواعد التالية دون أي تجاوز:\n"
        "1) أجب فقط اعتمادًا على نص المقطع المرفق أدناه، ولا تستخدم أي معرفة خارجية.\n"
        "2) اكتب الإجابة بالعربية الفصحى الرسمية بأسلوب واضح ومباشر.\n"
        "3) لا تؤلف معلومات، ولا تفترض أحكامًا غير موجودة في المقطع.\n"
        "4) إذا لم يكفِ المقطع للإجابة عن السؤال، وضّح ذلك بأدب دون إضافة معلومات من عندك.\n"
        "5) في نهاية الإجابة اذكر المصدر بهذا الشكل: "
        "المصدر: [اسم اللائحة] — [رقم المادة أو العنوان].\n\n"
        f"اسم اللائحة: {regulation_name}\n"
        f"رقم المادة أو العنوان: {article_number}\n"
        f"نص المقطع:\n{chunk_text}\n\n"
        f"سؤال الطالب: {question}\n\n"
        "الإجابة:"
    )


def ask_ai(question, chunk):
    # تجربة OpenRouter أولًا ثم Gemini كبديل اختياري
    prompt = build_prompt(question, chunk)
    errors = []

    providers = []

    if AI_PROVIDER == "gemini":
        providers = ["gemini", "openrouter"]
    else:
        providers = ["openrouter", "gemini"]

    for provider in providers:
        if provider == "openrouter":
            if not OPENROUTER_API_KEY:
                errors.append("OpenRouter: مفتاح API غير متوفر في ملف .env")
                continue
            try:
                return call_openrouter(prompt)
            except Exception as error:
                errors.append(f"OpenRouter: {error}")

        elif provider == "gemini":
            if not GEMINI_API_KEY:
                errors.append("Gemini: مفتاح API غير متوفر في ملف .env")
                continue
            try:
                return call_gemini(prompt)
            except Exception as error:
                errors.append(f"Gemini: {error}")

    if errors:
        raise ConnectionError("؛ ".join(errors))

    raise ConnectionError(
        "لم يتم العثور على مفتاح API صالح. "
        "يرجى إضافة OPENROUTER_API_KEY في ملف .env "
        "(أو GEMINI_API_KEY كبديل اختياري)."
    )


def _translate_http_error(status_code, provider_name):
    # تحويل رموز أخطاء HTTP إلى رسائل عربية واضحة
    if status_code == 401:
        return f"مفتاح {provider_name} غير صالح أو منتهي الصلاحية."
    if status_code == 402:
        return f"رصيد حساب {provider_name} غير كافٍ لإتمام الطلب."
    if status_code == 403:
        return f"تم رفض الوصول إلى خدمة {provider_name}."
    if status_code == 404:
        return (
            f"النموذج المحدد غير متوفر حاليًا في {provider_name}. "
            "حدّث قيمة OPENROUTER_MODEL في ملف .env إلى نموذج متاح."
        )
    if status_code == 429:
        return f"تم تجاوز حد الطلبات في {provider_name}. حاول لاحقًا."
    if status_code >= 500:
        return f"خادم {provider_name} غير متاح مؤقتًا."
    return f"استجابة خطأ من {provider_name} برقم {status_code}."


def call_gemini(prompt):
    if not GEMINI_API_KEY:
        raise ConnectionError("مفتاح Gemini API غير متوفر في ملف .env")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024,
        },
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
    except requests.exceptions.Timeout:
        raise ConnectionError("انتهت مهلة الاتصال بخدمة Gemini.")
    except requests.exceptions.ConnectionError:
        raise ConnectionError("تعذّر الاتصال بخدمة Gemini. تحقق من اتصال الإنترنت.")
    except requests.exceptions.RequestException:
        raise ConnectionError("حدث خطأ أثناء الاتصال بخدمة Gemini.")

    if response.status_code != 200:
        raise ConnectionError(_translate_http_error(response.status_code, "Gemini"))

    try:
        data = response.json()
    except ValueError:
        raise ConnectionError("استجابة غير متوقعة من Gemini API.")

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError):
        raise ConnectionError("استجابة غير متوقعة من Gemini API.")


def call_openrouter(prompt):
    if not OPENROUTER_API_KEY:
        raise ConnectionError("مفتاح OpenRouter API غير متوفر في ملف .env")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_SITE_URL,
        "X-Title": OPENROUTER_APP_NAME,
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1024,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.exceptions.Timeout:
        raise ConnectionError("انتهت مهلة الاتصال بخدمة OpenRouter.")
    except requests.exceptions.ConnectionError:
        raise ConnectionError("تعذّر الاتصال بخدمة OpenRouter. تحقق من اتصال الإنترنت.")
    except requests.exceptions.RequestException:
        raise ConnectionError("حدث خطأ أثناء الاتصال بخدمة OpenRouter.")

    if response.status_code != 200:
        detail = ""
        try:
            err = response.json().get("error")
            if isinstance(err, dict):
                detail = err.get("message", "")
            elif err:
                detail = str(err)
        except Exception:
            detail = ""
        base = _translate_http_error(response.status_code, "OpenRouter")
        if detail:
            raise ConnectionError(f"{base} التفاصيل: {detail}")
        raise ConnectionError(base)

    try:
        data = response.json()
    except ValueError:
        raise ConnectionError("استجابة غير متوقعة من OpenRouter API.")

    if "error" in data:
        error_message = data["error"]
        if isinstance(error_message, dict):
            error_message = error_message.get("message", "خطأ غير معروف")
        raise ConnectionError(f"رفض OpenRouter الطلب: {error_message}")

    try:
        content = data["choices"][0]["message"]["content"]
        if not content or not str(content).strip():
            raise ConnectionError("استجابة فارغة من OpenRouter API.")
        return str(content).strip()
    except (KeyError, IndexError, TypeError):
        raise ConnectionError("استجابة غير متوقعة من OpenRouter API.")
