import json
import os
import re
import time
import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import gradio as gr
from dotenv import load_dotenv
from pathlib import Path
import openai
from agent_memory_client import MemoryAPIClient, MemoryClientConfig
from agent_memory_client.integrations.langchain import get_memory_tools
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from memory_demo import __version__ as app_version
import logging
import base64

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============== Env & Clients ==============
load_dotenv()

LOGO_PATH = Path(__file__).parent / "public" / "logo.png"
LOGO_B64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")
LOGO_SRC = f"data:image/png;base64,{LOGO_B64}"
APP_PASSWORD = os.getenv("APP_PASSWORD", "password")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")
SESSION_ID = str(uuid.uuid4())

SYSTEM_PROMPT = {
    "role": "system",
    "content": """
    You are a helpful assistant. You can help with various types of questions.
    You have access to conversation history and memory management tools to provide personalized responses.

    Available tools:

    1. **web_search** (if available): Search for additional information when specifically needed.

    2. **Memory Management Tools** (always available):
       - **search_memory**: Look up previous conversations and stored information
       - **get_or_create_working_memory**: Check current session context
       - **lazily_create_long_term_memory**: Store important preferences or information
       - **update_working_memory_data**: Save session-specific data

    **Guidelines**:
    - Answer the user's actual question first and directly
    - When someone shares information (like "I like X"), simply acknowledge it naturally - don't immediately give advice or suggestions unless they ask
    - Search memory or web when it would be helpful for the current conversation
    - Be conversational and natural - respond to what the user actually says
    - When sharing memories, simply state what you remember rather than turning it into advice
    - Only offer suggestions, recommendations, or tips if the user explicitly asks for them
    - Store preferences and important details, but don't be overly eager about it
    - If someone shares a preference, respond like a friend would - acknowledge it, maybe ask a follow-up question, but don't launch into advice

    Be helpful, friendly, and responsive. Mirror their conversational style - if they're just chatting, chat back. If they ask for help, then help.
    """,
}

web_search_function = {
    "name": "web_search",
    "description": """
              Search the web for current information. Use this when you need up-to-date information that may
              not be in your training data.
            """,
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant information",
            }
        },
        "required": ["query"],
    },
}

available_functions = [web_search_function]

memory_client_config = MemoryClientConfig(
    base_url="http://localhost:8000"
)
memory_client = MemoryAPIClient(memory_client_config)
memory_tool_schemas = MemoryAPIClient.get_all_memory_tool_schemas()
for tool_schema in memory_tool_schemas:
    available_functions.append(tool_schema["function"])

logger.info(
    f"Available memory tools: {[tool['function']['name'] for tool in memory_tool_schemas]}"
)

llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0.7).bind_tools(
    available_functions
)

# ===================== CSS (VISUAL ONLY) =====================
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Space+Grotesk:wght@400;600;700&display=swap');

:root {
  --redis-red:#D82C20; --ink:#0b1220; --soft:#475569; --muted:#64748b;
  --line:#e5e7eb; --bg:#f6f7f9; --white:#ffffff; --radius:14px;
  --success:#10b981; --warning:#f59e0b;
}

* { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif; }
body, #app-root { background: var(--bg); }

/* HEADER */
.app-header {
  position: sticky; top: 0; z-index: 50;
  display:flex; align-items:center; justify-content:space-between; gap:12px;
  padding:14px 16px; background: var(--redis-red); color:#fff;
  box-shadow: 0 2px 8px rgba(0,0,0,.18);
}
.app-header .brand { display:flex; align-items:center; gap:14px; flex:1; }
.app-header .brand img { height:24px; display:block; }
.app-header .brand-content { display:flex; flex-direction:column; gap:4px; flex:1; }
.app-header .title {
  font-family: 'Space Grotesk', Inter, sans-serif;
  font-size:20px; font-weight:700; letter-spacing:.3px;
  line-height:1.2;
}
.app-header .meta {
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  font-size:12px; opacity:0.95; font-weight:500;
}
.app-header .meta-item {
  display:inline-flex; align-items:center; gap:6px;
  padding:3px 8px; background:rgba(255,255,255,0.15);
  border-radius:6px; white-space:nowrap;
}
.app-header .meta-item .label { opacity:0.8; }
.app-header .meta-item .value { font-weight:600; }
.app-header .links { display:flex; gap:8px; }
.app-header .links a {
  display:inline-flex; align-items:center; gap:8px; color:#fff; text-decoration:none;
  border:1px solid rgba(255,255,255,.35); padding:7px 12px; border-radius:999px; font-weight:600; font-size:12px;
  transition: background .15s ease, transform .15s ease;
}
.app-header .links a:hover { background: rgba(255,255,255,.14); transform: translateY(-1px); }

/* login */
.login-card {
  max-width: 400px;
  margin: 100px auto;
  padding: 40px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.login-header {
  align-items: center;
  text-align: center;
  margin-bottom: 30px;
}
.login-logo img {
  height: 40px !important;
  width: auto !important;
  object-fit: contain;
  margin: 0 auto 16px auto;
  display: block;
}
    
/* Mobile responsive header */
@media (max-width: 768px) {
  .app-header { flex-direction:column; align-items:flex-start; padding:12px; }
  .app-header .brand { flex-direction:column; align-items:flex-start; gap:10px; }
  .app-header .brand img { height:20px; }
  .app-header .title { font-size:16px; }
  .app-header .meta { gap:8px; }
  .app-header .meta-item { font-size:11px; padding:2px 6px; }
  .app-header .links { width:100%; justify-content:flex-start; }
}

/* HEADINGS */
.h1 {
  font-family: 'Space Grotesk', Inter, sans-serif;
  font-size:26px; font-weight:700; color:var(--ink); margin:16px 16px 6px;
}
.h2 {
  font-family: 'Space Grotesk', Inter, sans-serif;
  font-size:16px; font-weight:600; color:var(--soft); margin:0 16px 14px;
}

/* Config box (clean) */
.config-card {
  margin: 10px 16px 14px; padding:12px;
  background: var(--white);
  border:1px solid var(--line); border-radius: var(--radius);
}

/* KPIs */
.kpi-row { display:flex; gap:12px; margin: 0 16px 16px; flex-wrap: wrap; }
.kpi {
  flex:1; min-width: 140px; background: var(--white); border:1px solid var(--line); border-radius:12px;
  padding:14px 16px; transition: transform .2s ease, box-shadow .2s ease;
}
.kpi:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,.08); }
.kpi .kpi-num {
  font-family: 'Space Grotesk', Inter, sans-serif;
  font-size:24px; font-weight:700; color:var(--ink); line-height:1.1;
}
.kpi .kpi-label {
  font-size:11px; color:var(--muted); margin-top:6px;
  text-transform:uppercase; letter-spacing:.8px; font-weight:600;
}
.kpi-accent { border-color: var(--redis-red); border-width: 2px; }
.kpi-accent .kpi-num { color: var(--redis-red); }

/* Scenarios side by side */
.scenarios { display:grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 10px 16px; }
@media (max-width: 1024px) { .scenarios { grid-template-columns: 1fr; } }

.card {
  background: var(--white); border:2px solid var(--line); border-radius: var(--radius);
  padding:16px; transition: border-color .2s ease;
}
.card:hover { border-color: var(--redis-red); }
.card .card-title {
  font-family: 'Space Grotesk', Inter, sans-serif;
  font-size:18px; font-weight:700; color:var(--ink); margin-bottom:12px;
  display: flex; align-items: center; gap: 8px;
}

/* Source badges */
.source-badge {
  display: inline-block; padding: 4px 10px; border-radius: 6px;
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .5px;
}
.source-cache { background: #d1fae5; color: #065f46; }
.source-llm { background: #fef3c7; color: #92400e; }

/* History */
.dataframe { background: var(--white); border:1px solid var(--line); border-radius: var(--radius); }
.dataframe thead tr th { font-size:12px; font-weight:600; }
.dataframe tbody tr td { font-size:12px; }

/* Buttons */
button.primary, .gr-button-primary {
  background: var(--redis-red) !important; border-color: var(--redis-red) !important; color:#fff !important;
  font-weight: 600 !important; transition: all .2s ease !important;
}
button.primary:hover, .gr-button-primary:hover {
  background: #c02518 !important; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(216,44,32,.3) !important;
}

/* Secondary buttons */
.secondary-btn {
  background: var(--white) !important; border: 1px solid var(--line) !important;
  color: var(--soft) !important; font-weight: 600 !important;
}

/* --- HERO (title + subtitle) --- */
.hero {
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  margin: 16px;
  padding: 16px 18px;
}

.hero-title {
  font-family: 'Space Grotesk', Inter, sans-serif;
  font-size: 26px;
  font-weight: 700;
  color: var(--ink);      /* force high contrast */
  letter-spacing: .2px;
  margin: 0 0 8px 0;
}

.hero-sub {
  font-size: 14px;
  color: var(--soft);
  line-height: 1.6;
  margin: 0;
}

/* If in some theme the title is "black on black", ensures contrast: */
.h1 { color: var(--ink) !important; background: transparent !important; }
"""

async def chat_fn(message, history):
    reply = f"Echo: {message}"
    partial = ""

    for ch in reply:
        await asyncio.sleep(0.02)
        partial += ch
        yield partial

# ============== APP ==============
with gr.Blocks(title="Redis Memory Server Demo") as demo:
    st = gr.State({"hits": 0, "misses": 0, "saved_tokens": 0, "saved_usd": 0.0, "history": []})

    # Header with logo + links
    gr.HTML(f"""
      <div class="app-header">
        <div class="brand">
          <img src="{LOGO_SRC}" alt="Redis">
          <div class="brand-content">
            <div class="title">Redis Memory Server Demo</div>
            <div class="meta">
              <div class="meta-item">
                <span class="label">Version:</span>
                <span class="value">{app_version}</span>
              </div>
              <div class="meta-item">
                <span class="label">GitHub:</span>
                <span class="value">mminichino</span>
              </div>
            </div>
          </div>
        </div>
        <div class="links">
          <a href="https://www.linkedin.com/in/michael-minichino/" target="_blank" rel="noopener">💼 LinkedIn</a>
          <a href="https://redis.io/" target="_blank" rel="noopener">🔗 Redis</a>
          <a href="https://github.com/mminichino/redis-agent-memory-demo" target="_blank" rel="noopener">⭐ GitHub Repo</a>
        </div>
      </div>
    """)

    # Title + Subtitle
    gr.HTML("""
      <div class="hero">
        <div class="hero-title">Redis Memory Server Demo</div>
        <p class="hero-sub">
          This demo shows how Redis Agent Memory Server stores both short and long term memory.
        </p>
      </div>
    """)

    # Settings
    with gr.Group(elem_classes=["config-card"]):
        with gr.Accordion("How it works (details)", open=False):
            gr.Markdown("LONG_DESCRIPTION")

    # Scenarios A and B (side by side)
    with gr.Row(elem_classes=["scenarios"]):
        # --- Scenario A ---
        with gr.Column(elem_classes=["card"]):
            gr.Markdown("<div class='card-title'>Chat 🅰️</div>")
            gr.ChatInterface(
                fn=chat_fn,
            )

        # --- Scenario B ---
        with gr.Column(elem_classes=["card"]):
            gr.Markdown("<div class='card-title'>Chat 🅱️</div>")
            gr.ChatInterface(
                fn=chat_fn,
            )

# ============== PASSWORD PROTECTION ==============
def check_password(password):
    if password == APP_PASSWORD:
        return {
            login_box: gr.update(visible=False),
            main_app: gr.update(visible=True)
        }
    else:
        return {
            login_box: gr.update(visible=True),
            main_app: gr.update(visible=False)
        }

# Wrap the demo with password protection
with gr.Blocks(title="Redis Agent Memory Server Demo") as app:
    with gr.Column(visible=True, elem_id="login-container") as login_box:
        gr.HTML(f"""
            <div style="max-width: 400px; margin: 100px auto; padding: 40px; background: white; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <img src="{LOGO_SRC}" alt="Redis" style="height: 40px; margin-bottom: 16px;">
                    <h2 style="font-family: 'Space Grotesk', sans-serif; color: #0b1220; margin: 0;">Redis LangCache Demo</h2>
                    <p style="color: #64748b; margin-top: 8px;">Enter the password to access</p>
                </div>
            </div>
        """)
        with gr.Row():
            gr.HTML("<div style='flex: 1;'></div>")
            with gr.Column(scale=1, min_width=300):
                password_input = gr.Textbox(
                    label="🔒 Password",
                    type="password",
                    placeholder="Enter password...",
                    elem_id="password-input"
                )
                login_btn = gr.Button("Enter", variant="primary", size="lg")
                login_status = gr.HTML("")
            gr.HTML("<div style='flex: 1;'></div>")

    with gr.Column(visible=False) as main_app:
        demo.render()

    # Handle login
    def handle_login(password):
        if password == APP_PASSWORD:
            return {
                login_box: gr.update(visible=False),
                main_app: gr.update(visible=True),
                login_status: ""
            }
        else:
            return {
                login_box: gr.update(visible=True),
                main_app: gr.update(visible=False),
                login_status: "<p style='color: #ef4444; text-align: center; margin-top: 10px;'>❌ Incorrect password</p>"
            }

    login_btn.click(
        fn=handle_login,
        inputs=[password_input],
        outputs=[login_box, main_app, login_status]
    )

    password_input.submit(
        fn=handle_login,
        inputs=[password_input],
        outputs=[login_box, main_app, login_status]
    )

def main():
    app.launch(css=CUSTOM_CSS)

if __name__ == "__main__":
    main()
