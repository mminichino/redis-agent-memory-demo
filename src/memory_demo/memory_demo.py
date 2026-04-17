from __future__ import annotations
import os
import uuid
import gradio as gr
from gradio import ChatMessage
from dotenv import load_dotenv
from pathlib import Path
from memory_demo.driver import ChatWithMemory
from memory_demo import __version__ as app_version
import logging

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s [%(filename)s:%(lineno)d]",
    force=True,
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
error_trace_logger = logging.getLogger(f"{__name__}.error_trace")
error_trace_logger.setLevel(logging.ERROR)
error_trace_logger.propagate = False
if not any(isinstance(h, logging.FileHandler) and h.baseFilename.endswith("debug.log") for h in error_trace_logger.handlers):
    debug_file_handler = logging.FileHandler("debug.log")
    debug_file_handler.setLevel(logging.ERROR)
    debug_file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    error_trace_logger.addHandler(debug_file_handler)

# ============== Env & Clients ==============
load_dotenv()

LOGO_PATH = Path(__file__).parent / "public" / "logo.png"
LOGO_SRC = str(LOGO_PATH)
if "APP_PASSWORD" in os.environ:
    APP_PASSWORD = os.getenv("APP_PASSWORD")
else:
    APP_PASSWORD = "password"
logger.info(f"APP_PASSWORD: {APP_PASSWORD}")

ams_server_url = os.getenv("AGENT_MEMORY_SERVER_URL", "http://localhost:8000")
chat = ChatWithMemory(ams_url=ams_server_url, namespace="demo")

# ===================== THEME =====================
theme = gr.themes.Soft(
    primary_hue="slate",
    secondary_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
)

APP_CSS = """
/* Login: center logo and title */
.login-logo-row { justify-content: center !important; width: 100%; }
.login-title-wrap { text-align: center; max-width: 28rem; margin: 0 auto; }
.login-title-wrap h1 { margin-bottom: 0.35rem; font-size: 1.5rem; }
.login-title-wrap p { margin-top: 0; opacity: 0.85; }

/* Main app: header layout, no clipped logo */
.app-header { align-items: flex-start !important; flex-wrap: wrap; gap: 0.75rem 1rem; width: 100%; }
.app-header-logo { flex: 0 0 auto !important; min-width: 0 !important; }
.app-header-logo .image-container,
.app-header-logo img { max-width: 56px !important; height: auto !important; object-fit: contain; }
.app-header-title { flex: 1 1 12rem !important; min-width: 0 !important; }
.app-header-title h2 { margin: 0 0 0.25rem 0; line-height: 1.25; font-size: 1.35rem; }
.app-header-title p { margin: 0; }
.app-header-links { flex: 0 1 14rem !important; min-width: 0 !important; text-align: right; }
.app-header-links p { margin: 0; line-height: 1.5; }

/* Main column: avoid extra framed border */
#main-app-root.gr-column { border: none !important; box-shadow: none !important; outline: none !important; }

/* Login covers the app while keeping main content mounted (ChatInterface needs to render for first paint). */
.login-overlay {
  position: fixed !important;
  inset: 0 !important;
  z-index: 10000 !important;
  width: 100vw !important;
  max-width: 100vw !important;
  min-height: 100vh !important;
  background: var(--body-background-fill, #f8fafc) !important;
  overflow-y: auto !important;
  box-sizing: border-box !important;
}
"""

def _get_client_ip(request: gr.Request | None) -> str:
    if request is None:
        return "unknown"

    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()

    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"

def chat_fn(message, _, state):
    user_id = state.get("username", "guest")
    session_id = state.get("session_id", "guest")
    logger.info(f"Chat: user {user_id}: session {session_id}: message {message}")
    messages: list[ChatMessage] = []
    for msg in chat.process_input(message, session_id, user_id):
        if msg.type == "ai":
            chat_message = ChatMessage(role="assistant", content=msg.content or "")
        elif msg.type == "tool":
            chat_message = ChatMessage(role="system", content=f"Called tool: {msg.name}")
        else:
            continue
        messages.append(chat_message)
        yield messages

def session_md(state):
    username = state.get("username", "Guest")
    ams_url = state.get("ams_url", "Not set")
    session_id = state.get("session_id", "Not set")

    return f"""
- **Username:** {username}
- **Session ID:** {session_id}
- **Agent Memory Server URL:** {ams_url}
"""

# ============== Demo ==============
def render_demo():
    with gr.Row(elem_classes=["app-header"]):
        with gr.Column(scale=0, min_width=64, elem_classes=["app-header-logo"]):
            gr.Image(
                LOGO_SRC,
                show_label=False,
                container=False,
                height=56,
                width=56,
                interactive=False,
                buttons=[],
            )
        with gr.Column(scale=1, min_width=0, elem_classes=["app-header-title"]):
            gr.Markdown(
                f"## Redis Memory Server Demo\n**Version:** {app_version}",
            )
        with gr.Column(scale=0, min_width=200, elem_classes=["app-header-links"]):
            gr.Markdown(
                "[LinkedIn](https://www.linkedin.com/in/michael-minichino/) · "
                "[Redis](https://redis.io/) · "
                "[GitHub](https://github.com/mminichino/redis-agent-memory-demo)",
            )

    gr.Markdown(
        "This demo shows how Redis Agent Memory Server stores both short and long term memory."
    )

    gr.Markdown("### Session")
    session_box_md = gr.Markdown(session_md({}))

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Chat with Assistant")
            gr.ChatInterface(
                fn=chat_fn,
                chatbot=gr.Chatbot(height=600),
                additional_inputs=[st],
                show_progress="hidden",
            )
    
    with gr.Row():
        gr.HTML("<div style='flex: 1;'></div>")
        with gr.Column(scale=0, min_width=100):
            logout_button = gr.Button("Logout", variant="secondary", size="sm")
        gr.HTML("<div style='flex: 1;'></div>")

    return session_box_md, logout_button

# ============== PASSWORD PROTECTION ==============
with gr.Blocks(title="Redis Agent Memory Server Demo") as app:
    st = gr.State({"username": "", "ams_url": "", "history": [], "authenticated": False, "session_id": str(uuid.uuid4())})
    browser_state = gr.BrowserState()

    with gr.Column(visible=True, variant="compact", elem_classes=["login-overlay"]) as login_box:
        with gr.Row(elem_classes=["login-logo-row"]):
            gr.Image(
                LOGO_SRC,
                show_label=False,
                container=False,
                height=48,
                width=48,
                interactive=False,
                buttons=[],
            )
        gr.Markdown(
            "# Redis LangCache Demo\n\nEnter the password to access.",
            elem_classes=["login-title-wrap"],
        )
        with gr.Row():
            gr.HTML("<div style='flex: 1;'></div>")
            with gr.Column(scale=1, min_width=300):
                username_input = gr.Textbox(
                    label="🏷️ Username",
                    type="text",
                    placeholder="Enter your username",
                )
                password_input = gr.Textbox(
                    label="🔒 Password",
                    type="password",
                    placeholder="Enter password...",
                )
                login_btn = gr.Button("Enter", variant="primary", size="lg")
                login_status = gr.HTML("")
            gr.HTML("<div style='flex: 1;'></div>")

    with gr.Column(visible=True, elem_id="main-app-root"):
        session_box, logout_btn = render_demo()

    def handle_login(username, password, state, request: gr.Request):
        if password == APP_PASSWORD:
            session_id = str(uuid.uuid4())
            state["username"] = username
            state["ams_url"] = ams_server_url
            state["authenticated"] = True
            state["session_id"] = session_id
            browser_payload = {
                "session_id": session_id,
                "username": username,
            }
            return (
                gr.update(visible=False),
                "",
                state,
                session_md(state),
                browser_payload,
            )
        client_ip = _get_client_ip(request)
        logger.warning(f"Failed login attempt from IP: {client_ip}")
        state["authenticated"] = False
        return (
            gr.update(visible=True),
            "<p style='color: #ef4444; text-align: center; margin-top: 10px;'>❌ Incorrect password</p>",
            state,
            gr.skip(),
            gr.skip(),
        )

    def handle_logout(state):
        state["authenticated"] = False
        state["username"] = ""
        state["ams_url"] = ""
        return (
            gr.update(visible=True),
            "",
            state,
            session_md(state),
            {"session_id": "", "username": ""},
        )

    # Handle session load
    def check_session(_browser_state, state):
        if _browser_state is None:
            return {
                login_box: gr.update(visible=True),
                st: state,
                session_box: gr.update(),
            }
        session_id = _browser_state.get("session_id")
        username = _browser_state.get("username")
        
        if session_id and username:
            state["username"] = username
            state["session_id"] = session_id
            state["ams_url"] = ams_server_url
            state["authenticated"] = True
            return {
                login_box: gr.update(visible=False),
                st: state,
                session_box: session_md(state),
            }
        return {
            login_box: gr.update(visible=True),
            st: state,
            session_box: gr.update(),
        }

    login_btn.click(
        fn=handle_login,
        inputs=[username_input, password_input, st],
        outputs=[login_box, login_status, st, session_box, browser_state],
        show_progress="hidden",
    )

    password_input.submit(
        fn=handle_login,
        inputs=[username_input, password_input, st],
        outputs=[login_box, login_status, st, session_box, browser_state],
        show_progress="hidden",
    )

    logout_btn.click(
        fn=handle_logout,
        inputs=[st],
        outputs=[login_box, login_status, st, session_box, browser_state],
        show_progress="hidden",
    )

    app.load(
        fn=check_session,
        inputs=[browser_state, st],
        outputs=[login_box, st, session_box],
        show_progress="hidden",
    )

def main():
    app.launch(theme=theme, css=APP_CSS)

if __name__ == "__main__":
    main()
