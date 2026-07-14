const chatForm = document.getElementById("chatForm");
const questionInput = document.getElementById("questionInput");
const chatMessages = document.getElementById("chatMessages");
const sendButton = document.getElementById("sendButton");
const conversationList = document.getElementById("conversationList");
const sidebarEmpty = document.getElementById("sidebarEmpty");
const newChatBtn = document.getElementById("newChatBtn");
const sidebarToggle = document.getElementById("sidebarToggle");
const chatSidebar = document.getElementById("chatSidebar");

let currentConversationId = null;

const ICON_QUESTION =
    '<svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 15.2a1.2 1.2 0 1 1 0-2.4 1.2 1.2 0 0 1 0 2.4zm1.4-4.5c-.5.3-.9.6-.9 1.3h-1.8c0-1.3.7-2 1.4-2.4.6-.3 1-.6 1-1.2 0-.7-.6-1.2-1.5-1.2-.9 0-1.5.5-1.6 1.3H7.9C8.1 8.4 9.6 7.2 12 7.2c2.3 0 3.9 1.3 3.9 3.1 0 1.1-.6 1.9-1.5 2.4z"/>' +
    "</svg>";

const ICON_BOOK =
    '<svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path fill="currentColor" d="M6.5 3.5A2.5 2.5 0 0 0 4 6v12.2c0 .9.7 1.6 1.6 1.6H19a1 1 0 0 0 0-2H6.5a.5.5 0 0 1 0-1H19V4.5a1 1 0 0 0-1-1H6.5zm2 3h8v1.8h-8V6.5zm0 3.5h8V11h-8V10z"/>' +
    "</svg>";

const ICON_ALERT =
    '<svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path fill="currentColor" d="M12 3.2L2.6 19.4c-.3.5.1 1.1.7 1.1h17.4c.6 0 1-.6.7-1.1L12 3.2zM11 10h2v5h-2v-5zm0 6.5h2V18h-2v-1.5z"/>' +
    "</svg>";

const ICON_LOADING =
    '<svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path fill="currentColor" d="M12 4a8 8 0 0 1 8 8h-2.2A5.8 5.8 0 0 0 12 6.2V4zm0 16a8 8 0 0 1-8-8h2.2A5.8 5.8 0 0 0 12 17.8V20z"/>' +
    "</svg>";

if (chatForm) {
    chatForm.addEventListener("submit", function (event) {
        event.preventDefault();
        sendQuestion();
    });
}

if (newChatBtn) {
    newChatBtn.addEventListener("click", function () {
        startNewConversation();
    });
}

if (sidebarToggle && chatSidebar) {
    sidebarToggle.addEventListener("click", function () {
        chatSidebar.classList.toggle("is-open");
    });
}

if (conversationList) {
    loadConversations();
}

function sendQuestion() {
    const question = questionInput.value.trim();

    if (question.length < 3) {
        showError("السؤال قصير جدًا. يرجى كتابة سؤال أوضح.");
        return;
    }

    removeWelcomeMessage();
    appendQuestion(question);
    showLoading();
    setFormDisabled(true);

    const payload = { question: question };
    if (currentConversationId) {
        payload.conversation_id = currentConversationId;
    }

    fetch("/api/ask", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
    })
        .then(function (response) {
            return response.json().then(function (data) {
                return { status: response.status, data: data };
            });
        })
        .then(function (result) {
            removeLoading();

            if (result.status === 401) {
                window.location.href = "/login";
                return;
            }

            if (result.data.success) {
                currentConversationId = result.data.conversation_id;
                appendAnswer(result.data.answer, result.data.source);
                loadConversations();
            } else {
                showError(result.data.message || "حدث خطأ غير متوقع.");
            }
        })
        .catch(function () {
            removeLoading();
            showError("تعذّر الاتصال بالخادم. تأكد من تشغيل التطبيق ثم أعد المحاولة.");
        })
        .finally(function () {
            setFormDisabled(false);
            questionInput.value = "";
            questionInput.focus();
        });
}

function loadConversations() {
    fetch("/api/conversations")
        .then(function (response) {
            if (response.status === 401) {
                window.location.href = "/login";
                return null;
            }
            return response.json();
        })
        .then(function (data) {
            if (!data || !data.success) {
                return;
            }
            renderConversationList(data.conversations || []);
        })
        .catch(function () {
            showError("تعذّر تحميل قائمة المحادثات.");
        });
}

function renderConversationList(items) {
    conversationList.innerHTML = "";

    if (!items.length) {
        sidebarEmpty.classList.remove("is-hidden");
        return;
    }

    sidebarEmpty.classList.add("is-hidden");

    items.forEach(function (item) {
        const li = document.createElement("li");
        li.className = "conversation-item";
        if (item.id === currentConversationId) {
            li.classList.add("is-active");
        }

        const openBtn = document.createElement("button");
        openBtn.type = "button";
        openBtn.className = "conversation-open";
        openBtn.textContent = item.title;
        openBtn.addEventListener("click", function () {
            openConversation(item.id);
        });

        const deleteBtn = document.createElement("button");
        deleteBtn.type = "button";
        deleteBtn.className = "conversation-delete";
        deleteBtn.textContent = "حذف";
        deleteBtn.addEventListener("click", function (event) {
            event.stopPropagation();
            removeConversation(item.id);
        });

        li.appendChild(openBtn);
        li.appendChild(deleteBtn);
        conversationList.appendChild(li);
    });
}

function openConversation(conversationId) {
    fetch("/api/conversations/" + conversationId)
        .then(function (response) {
            return response.json().then(function (data) {
                return { status: response.status, data: data };
            });
        })
        .then(function (result) {
            if (!result.data.success) {
                showError(result.data.message || "تعذّر فتح المحادثة.");
                return;
            }

            currentConversationId = conversationId;
            chatMessages.innerHTML = "";

            result.data.messages.forEach(function (message) {
                if (message.role === "user") {
                    appendQuestion(message.content);
                } else {
                    appendAnswer(message.content, message.source);
                }
            });

            if (!result.data.messages.length) {
                chatMessages.innerHTML =
                    '<div class="welcome-message"><p class="welcome-text">محادثة فارغة. اكتب سؤالك للبدء.</p></div>';
            }

            loadConversations();
            if (window.innerWidth < 767 && chatSidebar) {
                chatSidebar.classList.remove("is-open");
            }
        })
        .catch(function () {
            showError("تعذّر فتح المحادثة.");
        });
}

function removeConversation(conversationId) {
    if (!window.confirm("هل تريد حذف هذه المحادثة نهائيًا؟")) {
        return;
    }

    fetch("/api/conversations/" + conversationId, {
        method: "DELETE",
    })
        .then(function (response) {
            return response.json().then(function (data) {
                return { status: response.status, data: data };
            });
        })
        .then(function (result) {
            if (!result.data.success) {
                showError(result.data.message || "تعذّر حذف المحادثة.");
                return;
            }

            if (currentConversationId === conversationId) {
                startNewConversation();
            } else {
                loadConversations();
            }
        })
        .catch(function () {
            showError("تعذّر حذف المحادثة.");
        });
}

function startNewConversation() {
    currentConversationId = null;
    chatMessages.innerHTML =
        '<div class="welcome-message"><p class="welcome-text">محادثة جديدة. اكتب سؤالك حول اللوائح وسيُحفظ تلقائيًا.</p></div>';
    loadConversations();
    questionInput.focus();
}

function removeWelcomeMessage() {
    const welcome = chatMessages.querySelector(".welcome-message");
    if (welcome) {
        welcome.remove();
    }
}

function appendQuestion(text) {
    const block = document.createElement("div");
    block.className = "message-block question-block";
    block.innerHTML =
        '<div class="message-label">' + ICON_QUESTION + "<span>سؤالك</span></div>" +
        '<p class="message-text"></p>';
    block.querySelector(".message-text").textContent = text;
    chatMessages.appendChild(block);
    scrollToBottom();
}

function appendAnswer(text, source) {
    const block = document.createElement("div");
    block.className = "message-block answer-block";

    let sourceHtml = "";
    if (source) {
        sourceHtml =
            '<div class="source-info">' +
            '<p class="source-title">المصدر: ' +
            escapeHtml(source.regulation_name) +
            " — " +
            escapeHtml(source.article_number) +
            "</p>" +
            '<p class="source-text">' +
            escapeHtml(source.chunk_text) +
            "</p>" +
            "</div>";
    }

    block.innerHTML =
        '<div class="message-label">' + ICON_BOOK + "<span>إجابة الناظم</span></div>" +
        '<p class="message-text"></p>' +
        sourceHtml;

    block.querySelector(".message-text").textContent = text;
    chatMessages.appendChild(block);
    scrollToBottom();
}

function showError(message) {
    const block = document.createElement("div");
    block.className = "error-message";
    block.innerHTML =
        '<div class="message-label">' + ICON_ALERT + "<span>تنبيه</span></div>" +
        '<p class="error-text"></p>';
    block.querySelector(".error-text").textContent = message;
    chatMessages.appendChild(block);
    scrollToBottom();
}

function showLoading() {
    const block = document.createElement("div");
    block.className = "loading-indicator";
    block.id = "loadingIndicator";
    block.innerHTML =
        ICON_LOADING +
        '<span class="loading-text">جاري البحث في اللوائح وتوليد الإجابة...</span>';
    chatMessages.appendChild(block);
    scrollToBottom();
}

function removeLoading() {
    const loading = document.getElementById("loadingIndicator");
    if (loading) {
        loading.remove();
    }
}

function setFormDisabled(disabled) {
    questionInput.disabled = disabled;
    sendButton.disabled = disabled;
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
