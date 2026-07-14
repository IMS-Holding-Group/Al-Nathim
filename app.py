from flask import Flask, redirect, render_template, send_from_directory, session, url_for

from config import BASE_DIR, SECRET_KEY
from database.db import get_user_by_id, init_database
from routes.api_routes import api_bp
from routes.auth_routes import auth_bp, login_required


def create_app():
    # إنشاء تطبيق Flask وتسجيل المسارات
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    # تهيئة قاعدة البيانات عند بدء التشغيل
    init_database()

    # تسجيل المسارات
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)

    @app.context_processor
    def inject_user():
        user = None
        user_id = session.get("user_id")
        if user_id:
            user = get_user_by_id(user_id)
        return {"current_user": user}

    @app.route("/")
    def index():
        # عرض الصفحة الرئيسية التعريفية
        return render_template("index.html")

    @app.route("/chat")
    @login_required
    def chat():
        # عرض صفحة المحادثة الفرعية للمستخدم المسجّل
        return render_template("chat.html")

    @app.route("/assets/<path:filename>")
    def serve_assets(filename):
        # تقديم ملفات الشعار والخطوط من مجلد assets
        return send_from_directory(BASE_DIR / "assets", filename)

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(debug=True, host="0.0.0.0", port=5000)
