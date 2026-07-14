from functools import wraps

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import create_user, get_user_by_email, get_user_by_id

auth_bp = Blueprint("auth", __name__)


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


def api_login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            from flask import jsonify
            return jsonify({
                "success": False,
                "message": "يلزم تسجيل الدخول لإكمال هذا الطلب.",
            }), 401
        return view_func(*args, **kwargs)

    return wrapped


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("chat"))

    error = None

    if request.method == "POST":
        try:
            full_name = (request.form.get("full_name") or "").strip()
            email = (request.form.get("email") or "").strip()
            password = request.form.get("password") or ""
            password_confirm = request.form.get("password_confirm") or ""

            if len(full_name) < 3:
                error = "يرجى إدخال الاسم الكامل بشكل صحيح."
            elif "@" not in email or "." not in email:
                error = "يرجى إدخال بريد إلكتروني صالح."
            elif len(password) < 6:
                error = "كلمة المرور يجب أن تكون 6 أحرف على الأقل."
            elif password != password_confirm:
                error = "كلمتا المرور غير متطابقتين."
            else:
                password_hash = generate_password_hash(password)
                user_id = create_user(full_name, email, password_hash)
                if user_id is None:
                    error = "هذا البريد مسجّل مسبقًا. جرّب تسجيل الدخول."
                else:
                    session.clear()
                    session["user_id"] = user_id
                    session["user_name"] = full_name
                    return redirect(url_for("chat"))
        except Exception as err:
            print(f"خطأ في التسجيل: {err}")
            error = "تعذّر إنشاء الحساب. حاول مرة أخرى."

    return render_template("register.html", error=error)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("chat"))

    error = None
    next_url = request.args.get("next") or request.form.get("next") or url_for("chat")

    if request.method == "POST":
        try:
            email = (request.form.get("email") or "").strip()
            password = request.form.get("password") or ""
            user = get_user_by_email(email)

            if not user or not check_password_hash(user["password_hash"], password):
                error = "البريد الإلكتروني أو كلمة المرور غير صحيحة."
            else:
                session.clear()
                session["user_id"] = user["id"]
                session["user_name"] = user["full_name"]
                if next_url.startswith("/"):
                    return redirect(next_url)
                return redirect(url_for("chat"))
        except Exception as err:
            print(f"خطأ في تسجيل الدخول: {err}")
            error = "تعذّر تسجيل الدخول. حاول مرة أخرى."

    return render_template("login.html", error=error, next_url=next_url)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))
