from __future__ import annotations
import json
import os
import uuid
import time
from typing import Optional, AsyncGenerator, Any
import gradio as gr
from gradio import ChatMessage
from gradio.components.chatbot import MetadataDict
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path
from agent_memory_client import MemoryAPIClient, MemoryClientConfig
from agent_memory_client.models import WorkingMemory, MemoryRecord, MemoryMessage
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from memory_demo import __version__ as app_version
import logging
import traceback

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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2-chat-latest")
AGENT_MEMORY_SERVER_URL = os.getenv("AGENT_MEMORY_SERVER_URL", "http://localhost:8000")
ERROR_COUNT = 0

SYSTEM_PROMPT = {
    "role": "system",
    "content": """
    You are a helpful assistant with access to web search and memory tools.

    ## Primary goal
    Answer the user's question clearly and directly.

    ## Tool-use policy
    - Use `web_search` for current, live, recent, or time-sensitive information.
    - Use memory tools for stored user preferences, prior conversation context, or session-specific data.
    - If the question depends on freshness, prefer `web_search` instead of guessing.
    - If the question depends on memory, use the appropriate memory tool instead of asking the user to repeat themselves.
    - When a tool is needed, call it rather than answering from unsupported assumptions.

    ## User isolation
    All memory tools apply only to the current logged-in user. Do not pass a different user_id in tool arguments.

    ## Long Term Memory policy
    Store preferences or profile information as semantic records in long term memory.
    - durable preferences
    - stable traits
    Store episodic facts and time-bound knowledge as episodic records in long term memory.
    - user defaults
    - scheduled or recurring events
    - important episodic facts
    
    Do not store trivial, temporary, or low-value details.
    
    ## Response style
    - Answer the user's actual question first and directly
    - When someone shares information acknowledge it naturally, don't give advice or suggestions unless they ask
    - Be conversational and natural - respond to what the user actually says
    - When sharing memories, simply state what you remember rather than turning it into advice
    - Only offer suggestions, recommendations, or tips if the user explicitly asks for them
    - If someone shares a preference, respond like a friend would, don't launch into advice

    ## Output behavior
    - Prefer tool calls over guessing when external or stored information is needed.
    - Use the result of the tool call to formulate the final answer.
    """,
    "created_at": datetime.now(timezone.utc).isoformat(),
}

if "TAVILY_API_KEY" not in os.environ:
    logger.warning("TAVILY_API_KEY not found in environment. Web search will fail.")

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
    base_url=AGENT_MEMORY_SERVER_URL
)
memory_client = MemoryAPIClient(memory_client_config)
memory_tool_schemas = MemoryAPIClient.get_all_memory_tool_schemas()
for tool_schema in memory_tool_schemas:
    available_functions.append(tool_schema["function"])

logger.info(
    f"Available memory tools: {[tool['function']['name'] for tool in memory_tool_schemas]}"
)

llm = ChatOpenAI(model=OPENAI_MODEL).bind_tools(
    available_functions
)

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


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, MemoryRecord):
            return obj.model_dump()
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


def increment_error_count() -> None:
    global ERROR_COUNT
    ERROR_COUNT += 1
    tb_text = traceback.format_exc()
    error_trace_logger.error(tb_text)


async def _get_namespace(user_id: str) -> str:
    return f"demo_agent:{user_id}"


def _scoped_tool_arguments(function_name: str, arguments: str, user_id: str) -> str:
    try:
        args = json.loads(arguments) if arguments and str(arguments).strip() else {}
    except (json.JSONDecodeError, TypeError):
        increment_error_count()
        return arguments if isinstance(arguments, str) else json.dumps(arguments or {})
    if function_name == "search_memory" and user_id:
        args["user_id"] = user_id
    return json.dumps(args)


async def _get_working_memory(session_id: str, user_id: str) -> WorkingMemory:
    logger.info(f"Get working memory: {user_id} ({session_id})")
    created, result = await memory_client.get_or_create_working_memory(
        session_id=session_id,
        user_id=user_id,
        namespace=await _get_namespace(user_id),
        model_name="gpt-5.2-chat-latest",
    )
    return WorkingMemory(**result.model_dump())


async def _add_message_to_working_memory(session_id: str, user_id: str, role: str, content: str):
    logger.info(f"Add to working memory: {user_id} ({session_id}) {role}")
    new_message = MemoryMessage(
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc)
    )
    await memory_client.append_messages_to_working_memory(
        session_id=session_id,
        messages=[new_message],
        namespace=await _get_namespace(user_id),
        user_id=user_id,
        model_name="gpt-5.2-chat-latest",
    )


def _assistant_content_str(msg: Any) -> str:
    """Normalize LangChain AIMessage content for Gradio (str or multimodal list)."""
    c = getattr(msg, "content", None)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for block in c:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(c) if c is not None else ""


async def _search_web(query: str) -> str:
    try:
        logger.info(f"Searching the web for: {query}")
        tool = TavilySearch(max_results=3)
        response = tool.invoke(query)
        if isinstance(response, str):
            return response

        if isinstance(response, dict):
            results = response.get("results", [])
        elif isinstance(response, list):
            results = response
        else:
            results = []

        formatted_results = []
        for result in results:
            if not isinstance(result, dict):
                continue
            title = result.get("title", "No title")
            content = result.get("content", "No content")
            url = result.get("url", "No URL")
            formatted_results.append(f"**{title}**\n{content}\nSource: {url}")

        if not formatted_results:
            return "No relevant search results found."

        return "\n\n".join(formatted_results)
    except Exception as e:
        increment_error_count()
        logger.error(f"Error performing web search: {e}")
        return f"Error performing web search: {str(e)}"


async def _generate_response(
        session_id: str,
        user_id: str,
        context_messages: Optional[list[dict[str, str]]],
        iteration: Optional[int] = 1,
) -> AsyncGenerator[ChatMessage]:
    logger.info(f"Generate: {user_id} ({session_id}) iteration {iteration} with {len(context_messages)} messages")
    try:
        current_message = context_messages[-1]
        msg_role = current_message.get("role", "none")
        msg_content = current_message.get("content", "")
        logger.info(f"Role: {msg_role}")
        if current_message.get('role') == "user":
            logger.info(f"Content: {msg_content}")
            await _add_message_to_working_memory(
                session_id, user_id, "user", msg_content
            )

        response = llm.invoke(context_messages)

        tool_calls = getattr(response, "tool_calls", [])
        logger.debug(f"Tools to call:\n{json.dumps(tool_calls, indent=2)}")

        if not tool_calls and hasattr(response, "additional_kwargs"):
            tool_calls = response.additional_kwargs.get("tool_calls", [])

        if tool_calls and len(tool_calls) > 0:
            normalized_calls: list[dict] = []
            for idx, tc in enumerate(tool_calls):
                if isinstance(tc, dict):
                    if tc.get("type") == "function" and "function" in tc:
                        normalized_calls.append(tc)
                    else:
                        name = tc.get("function", {}).get("name", tc.get("name", ""))
                        args_value = tc.get("function", {}).get(
                            "arguments", tc.get("args", {})
                        )
                        if not isinstance(args_value, str):
                            try:
                                args_value = json.dumps(args_value)
                            except Exception as e:
                                increment_error_count()
                                logger.error(f"Error serializing args: {e}")
                                args_value = "{}"
                        normalized_calls.append(
                            {
                                "id": tc.get("id", f"tool_call_{idx}"),
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": args_value,
                                },
                            }
                        )
                else:
                    name = getattr(tc, "name", "")
                    args = getattr(tc, "args", {})
                    if not isinstance(args, str):
                        try:
                            args = json.dumps(args)
                        except Exception as e:
                            increment_error_count()
                            logger.error(f"Error serializing tool call args: {e}")
                            args = "{}"
                    normalized_calls.append(
                        {
                            "id": getattr(tc, "id", f"tool_call_{idx}"),
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": args,
                            },
                        }
                    )

            results = []
            logger.debug(f"Normalized tool calls:\n{json.dumps(normalized_calls, indent=2)}")
            for call in normalized_calls:
                fname = call.get("function", {}).get("name", "")
                start_time = time.time()
                try:
                    logger.info(f"Calling tool: {fname}")
                    if fname == "web_search":
                        args = json.loads(call.get("function", {}).get("arguments", "{}"))
                        res_content = await _search_web(args.get("query", ""))
                        res = {
                            "success": True,
                            "function_name": fname,
                            "result": res_content,
                            "formatted_response": res_content
                        }
                    else:
                        raw_args = call.get("function", {}).get("arguments", "{}")
                        if isinstance(raw_args, dict):
                            raw_args = json.dumps(raw_args)
                        res = await memory_client.resolve_tool_call(
                            tool_call={
                                "name": fname,
                                "arguments": _scoped_tool_arguments(
                                    fname, raw_args, user_id
                                ),
                            },
                            session_id=session_id,
                            namespace=await _get_namespace(user_id),
                            user_id=user_id,
                        )
                except Exception as e:
                    increment_error_count()
                    logger.error(f"Tool '{fname}' failed: {e}")
                    res = {"success": False, "error": str(e)}
                yield ChatMessage(
                    content="",
                    metadata=MetadataDict(
                        title=f"Called tool {fname}",
                        id=0,
                        status="done",
                        duration=time.time() - start_time
                    )
                )
                results.append((call, res))

            for i, (tc, res) in enumerate(results):
                logger.info(f"Tool {res.get('function_name', 'unknown')} success: {res.get('success', False)}")
                logger.debug(f"Tool calls result #{i}:\n{json.dumps(res, cls=CustomEncoder, indent=2)}")

            assistant_tools_msg = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": normalized_calls,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            tool_messages: list[dict] = []
            for i, (tc, res) in enumerate(results):
                if not res.get("success", False):
                    increment_error_count()
                    content = f"Error calling tool '{tc.get('function', {}).get('name', '')}': {res.get('error')}"
                else:
                    payload = res.get("result")
                    try:
                        content = (
                            json.dumps(payload, cls=CustomEncoder)
                            if isinstance(payload, (dict, list))
                            else str(res.get("formatted_response", ""))
                        )
                    except Exception as e:
                        increment_error_count()
                        logger.error(f"Error serializing payload: {e}")
                        content = str(res.get("formatted_response", ""))
                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"tool_call_{i}"),
                        "name": tc.get("function", {}).get("name", ""),
                        "content": content,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

            messages = (
                    context_messages + [assistant_tools_msg] + tool_messages
            )

            async for resp in _generate_response(session_id, user_id, messages, iteration + 1):
                yield resp
        elif response.content is not None:
            text = _assistant_content_str(response)
            await _add_message_to_working_memory(
                session_id, user_id, "assistant", text
            )
            yield ChatMessage(
                content=text,
            )
    except Exception as e:
        increment_error_count()
        logger.error(f"Error generating response: {e}", exc_info=True)
        yield ChatMessage(
            content="I'm sorry, I encountered an error processing your request.",
        )

async def process_user_input(
        user_input: str,
        session_id: str,
        user_id: str,
) -> AsyncGenerator[ChatMessage]:
    logger.info(f"Process user input: user {user_id}: session {session_id}: message {user_input}")
    try:
        working_memory = await _get_working_memory(session_id, user_id)
        context_messages: list[dict[str, str]] = [msg.model_dump(include={'role', 'content'}) for msg in working_memory.messages]
        context_messages.insert(0, SYSTEM_PROMPT)
        context_messages.append({"role": "user", "content": user_input})

        async for message in _generate_response(
            session_id, user_id, context_messages
        ):
            if not message:
                continue
            yield message
    except Exception as e:
        increment_error_count()
        logger.exception(f"Error processing user input: {e}")
        yield ChatMessage(
            content="I'm sorry, I encountered an error processing your request."
        )

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

async def chat_fn(message, _, state):
    user_id = state.get("username", "guest")
    session_id = state.get("session_id", "guest")
    logger.info(f"Chat: user {user_id}: session {session_id}: message {message}")
    messages: list[ChatMessage] = []
    async for message in process_user_input(message, session_id, user_id):
        messages.append(message)
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
            state["ams_url"] = AGENT_MEMORY_SERVER_URL
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
        increment_error_count()
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
            state["ams_url"] = AGENT_MEMORY_SERVER_URL
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
