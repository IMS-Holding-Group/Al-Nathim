from flask import Blueprint, jsonify, request, session

from database.db import (
    add_message,
    create_conversation,
    delete_conversation,
    get_conversation_for_user,
    get_conversation_messages,
    get_user_conversations,
    rename_conversation,
    save_qa_log,
    search_regulation_chunks,
)
from routes.auth_routes import api_login_required
from services.ai_service import ask_ai

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/ask", methods=["POST"])
@api_login_required
def ask_question():
    try:
        data = request.get_json(silent=True)
        user_id = session["user_id"]

        if not data or not data.get("question"):
            return jsonify({
                "success": False,
                "message": "يرجى إدخال سؤال صالح.",
            }), 400

        question = data["question"].strip()
        conversation_id = data.get("conversation_id")

        if len(question) < 3:
            return jsonify({
                "success": False,
                "message": "السؤال قصير جدًا. يرجى كتابة سؤال أوضح.",
            }), 400

        if conversation_id:
            conversation = get_conversation_for_user(int(conversation_id), user_id)
            if not conversation:
                return jsonify({
                    "success": False,
                    "message": "المحادثة غير موجودة أو غير مصرّح لك بالوصول إليها.",
                }), 404
            conversation_id = conversation["id"]
        else:
            conversation_id = create_conversation(user_id, question)

        matched_chunk = search_regulation_chunks(question)

        if not matched_chunk:
            return jsonify({
                "success": False,
                "message": (
                    "لم يتم العثور على مقطع مطابق في اللوائح المتاحة حاليًا. "
                    "جرّب صياغة السؤال بكلمات مختلفة."
                ),
            }), 404

        answer = ask_ai(question, matched_chunk)
        source = {
            "regulation_name": matched_chunk["regulation_name"],
            "article_number": matched_chunk["article_number"],
            "chunk_text": matched_chunk["chunk_text"],
        }

        add_message(conversation_id, "user", question)
        add_message(conversation_id, "assistant", answer, source)
        save_qa_log(question, answer)

        return jsonify({
            "success": True,
            "question": question,
            "answer": answer,
            "conversation_id": conversation_id,
            "source": source,
        }), 200

    except ConnectionError as error:
        return jsonify({
            "success": False,
            "message": (
                "تعذّر الاتصال بخدمة الذكاء الاصطناعي. "
                f"التفاصيل: {str(error)}"
            ),
        }), 503

    except Exception as error:
        print(f"خطأ غير متوقع في /api/ask: {error}")
        return jsonify({
            "success": False,
            "message": "حدث خطأ داخلي أثناء معالجة السؤال. يرجى المحاولة لاحقًا.",
        }), 500


@api_bp.route("/api/conversations", methods=["GET"])
@api_login_required
def list_conversations():
    try:
        items = get_user_conversations(session["user_id"])
        return jsonify({"success": True, "conversations": items}), 200
    except Exception as error:
        print(f"خطأ في جلب المحادثات: {error}")
        return jsonify({
            "success": False,
            "message": "تعذّر جلب قائمة المحادثات.",
        }), 500


@api_bp.route("/api/conversations/<int:conversation_id>", methods=["GET"])
@api_login_required
def get_conversation(conversation_id):
    try:
        data = get_conversation_messages(conversation_id, session["user_id"])
        if not data:
            return jsonify({
                "success": False,
                "message": "المحادثة غير موجودة.",
            }), 404
        return jsonify({"success": True, **data}), 200
    except Exception as error:
        print(f"خطأ في جلب المحادثة: {error}")
        return jsonify({
            "success": False,
            "message": "تعذّر جلب المحادثة.",
        }), 500


@api_bp.route("/api/conversations/<int:conversation_id>", methods=["DELETE"])
@api_login_required
def remove_conversation(conversation_id):
    try:
        deleted = delete_conversation(conversation_id, session["user_id"])
        if not deleted:
            return jsonify({
                "success": False,
                "message": "تعذّر حذف المحادثة أو أنها غير موجودة.",
            }), 404
        return jsonify({
            "success": True,
            "message": "تم حذف المحادثة بنجاح.",
        }), 200
    except Exception as error:
        print(f"خطأ في حذف المحادثة: {error}")
        return jsonify({
            "success": False,
            "message": "حدث خطأ أثناء حذف المحادثة.",
        }), 500


@api_bp.route("/api/conversations/<int:conversation_id>", methods=["PATCH"])
@api_login_required
def update_conversation(conversation_id):
    try:
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        if len(title) < 2:
            return jsonify({
                "success": False,
                "message": "عنوان المحادثة قصير جدًا.",
            }), 400

        updated = rename_conversation(conversation_id, session["user_id"], title)
        if not updated:
            return jsonify({
                "success": False,
                "message": "تعذّر تعديل عنوان المحادثة.",
            }), 404

        return jsonify({
            "success": True,
            "message": "تم تحديث عنوان المحادثة.",
        }), 200
    except Exception as error:
        print(f"خطأ في تعديل المحادثة: {error}")
        return jsonify({
            "success": False,
            "message": "حدث خطأ أثناء تعديل المحادثة.",
        }), 500


@api_bp.route("/api/conversations", methods=["POST"])
@api_login_required
def new_conversation():
    try:
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "محادثة جديدة").strip()
        conversation_id = create_conversation(session["user_id"], title)
        return jsonify({
            "success": True,
            "conversation_id": conversation_id,
            "title": title[:80],
        }), 201
    except Exception as error:
        print(f"خطأ في إنشاء محادثة: {error}")
        return jsonify({
            "success": False,
            "message": "تعذّر إنشاء محادثة جديدة.",
        }), 500
