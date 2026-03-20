from __future__ import annotations
import json
import os
import uuid
from typing import Optional
import gradio as gr
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path
from agent_memory_client import MemoryAPIClient, MemoryClientConfig
from agent_memory_client.models import WorkingMemory, MemoryRecord
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from memory_demo import __version__ as app_version
import logging
import base64
import secrets
import string

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============== Env & Clients ==============
load_dotenv()

LOGO_PATH = Path(__file__).parent / "public" / "logo.png"
LOGO_B64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")
LOGO_SRC = f"data:image/png;base64,{LOGO_B64}"
if "APP_PASSWORD" in os.environ:
    APP_PASSWORD = os.getenv("APP_PASSWORD")
else:
    characters = string.ascii_letters + string.digits
    APP_PASSWORD = ''.join(secrets.choice(characters) for _ in range(16))
    logger.info(f"APP_PASSWORD: {APP_PASSWORD}")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2-chat-latest")
AGENT_MEMORY_SERVER_URL = os.getenv("AGENT_MEMORY_SERVER_URL", "http://localhost:8000")

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

# ===================== CSS =====================
CUSTOM_CSS = """
#login-container {
    align-items: center;
}
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.145 0 0);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  --primary-foreground: oklch(0.985 0 0);
  --secondary: oklch(0.97 0 0);
  --secondary-foreground: oklch(0.205 0 0);
  --muted: oklch(0.97 0 0);
  --muted-foreground: oklch(0.556 0 0);
  --accent: oklch(0.97 0 0);
  --accent-foreground: oklch(0.205 0 0);
  --destructive: oklch(0.577 0.245 27.325);
  --destructive-foreground: oklch(0.577 0.245 27.325);
  --border: oklch(0.922 0 0);
  --input: oklch(0.922 0 0);
  --ring: oklch(0.708 0 0);
  --radius: 0.625rem;

  /* Redis Specific Branding */
  --redis-red: #D82C20;
}

* { font-family: Inter, system-ui, -apple-system, sans-serif; border-color: var(--border); }

body, #app-root { 
  background: var(--background); 
  color: var(--foreground);
}

/* HEADER */
.app-header {
  position: sticky; top: 0; z-index: 50;
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 14px 16px; background: var(--redis-red); color: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,.18);
}
.app-header .brand { display: flex; align-items: center; gap: 14px; flex: 1; }
.app-header .brand img { height: 24px; display: block; }
.app-header .brand-content { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.app-header .title {
  font-family: 'Space Grotesk', Inter, sans-serif;
  font-size: 20px; font-weight: 700; letter-spacing: .3px;
  line-height: 1.2;
}
.app-header .meta {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  font-size: 12px; opacity: 0.95; font-weight: 500;
}
.app-header .meta-item {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 8px; background: rgba(255,255,255,0.15);
  border-radius: 6px; white-space: nowrap;
}
.app-header .meta-item .label { opacity: 0.8; }
.app-header .meta-item .value { font-weight: 600; }
.app-header .links { display: flex; gap: 8px; }
.app-header .links a {
  display: inline-flex; align-items: center; gap: 8px; color: #fff; text-decoration: none;
  border: 1px solid rgba(255,255,255,.35); padding: 7px 12px; border-radius: 999px; font-weight: 600; font-size: 12px;
  transition: background .15s ease, transform .15s ease;
}
.app-header .links a:hover { background: rgba(255,255,255,.14); transform: translateY(-1px); }

/* Mobile responsive header */
@media (max-width: 768px) {
  .app-header { flex-direction: column; align-items: flex-start; padding: 12px; }
  .app-header .brand { flex-direction: column; align-items: flex-start; gap: 10px; }
  .app-header .brand img { height: 20px; }
  .app-header .title { font-size: 16px; }
  .app-header .meta { gap: 8px; }
  .app-header .meta-item { font-size: 11px; padding: 2px 6px; }
  .app-header .links { width: 100%; justify-content: flex-start; }
}

/* Config box */
.config-card {
  margin: 10px 16px 14px; padding: 12px;
  background: var(--card);
  border: 1px solid var(--border); border-radius: var(--radius);
  color: var(--card-foreground);
}

.chat-window { display: flex; justify-content: center; margin: 10px 16px; }
.chat-window > * { width: 100%; max-width: 1200px; }

.card {
  background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 16px; transition: border-color .2s ease;
  color: var(--card-foreground);
}
.card:hover { border-color: var(--redis-red); }
.card .card-title {
  font-family: 'Space Grotesk', Inter, sans-serif;
  font-size: 18px; font-weight: 700; color: var(--foreground); margin-bottom: 12px;
  display: flex; align-items: center; gap: 8px;
}

/* Buttons */
button.primary, .gr-button-primary {
  background: var(--redis-red) !important; border-color: var(--redis-red) !important; color: #fff !important;
  font-weight: 600 !important; transition: all .2s ease !important;
  border-radius: var(--radius) !important;
}
button.primary:hover, .gr-button-primary:hover {
  background: #c02518 !important; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(216,44,32,.3) !important;
}

.hero {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin: 16px;
  padding: 16px 18px;
  color: var(--card-foreground);
}

.hero-title {
  font-family: 'Space Grotesk', Inter, sans-serif;
  font-size: 26px;
  font-weight: 700;
  color: var(--foreground);
  letter-spacing: .2px;
  margin: 0 0 8px 0;
}

.hero-sub {
  font-size: 14px;
  color: var(--muted-foreground);
  line-height: 1.6;
  margin: 0;
}

/* Chat interface buttons */
.chat-window button.secondary-small {
  padding: 4px 8px !important;
  font-size: 12px !important;
  height: auto !important;
  min-width: unset !important;
  border: none !important;
  background: transparent !important;
  color: var(--muted-foreground) !important;
  box-shadow: none !important;
}

.chat-window button.secondary-small:hover {
  color: var(--foreground) !important;
  background: var(--secondary) !important;
}

.chat-window .message-row button {
  padding: 2px 6px !important;
  font-size: 11px !important;
  height: auto !important;
  min-width: unset !important;
  border: none !important;
  background: transparent !important;
  color: var(--muted-foreground) !important;
  box-shadow: none !important;
}

.chat-window .message-row button:hover {
  color: var(--foreground) !important;
  background: var(--secondary) !important;
}

.chat-window .message-row button svg {
  width: 14px !important;
  height: 14px !important;
}

.chat-window button.secondary-small svg {
  width: 16px !important;
  height: 16px !important;
}

.chat-window .message-row button svg,
.chat-window button.secondary-small svg {
  stroke-width: 1.5px !important;
}
"""

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, MemoryRecord):
            return obj.model_dump()
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)

async def _get_namespace(user_id: str) -> str:
    return f"demo_agent:{user_id}"

async def _get_working_memory(session_id: str, user_id: str) -> WorkingMemory:
    created, result = await memory_client.get_or_create_working_memory(
        session_id=session_id,
        namespace=await _get_namespace(user_id),
        model_name="gpt-5.2-chat-latest",
    )
    return WorkingMemory(**result.model_dump())

async def _add_message_to_working_memory(session_id: str, user_id: str, role: str, content: str):
    new_message = [
        {
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    await memory_client.get_or_create_working_memory(
        session_id=session_id,
        namespace=await _get_namespace(user_id),
        model_name="gpt-5.2-chat-latest",
    )
    await memory_client.append_messages_to_working_memory(
        session_id=session_id,
        messages=new_message,
        namespace=await _get_namespace(user_id),
    )

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
        logger.error(f"Error performing web search: {e}")
        return f"Error performing web search: {str(e)}"

async def _handle_web_search_call(function_call: dict) -> str:
    logger.info("Searching the web")
    try:
        function_args = json.loads(function_call["arguments"])
        query = function_args.get("query", "")
        return await _search_web(query)
    except (json.JSONDecodeError, TypeError):
        logger.error(f"Invalid web search arguments: {function_call}")
        return "I'm sorry, I encountered an error processing your web search request. Please try again."

async def _handle_memory_tool_call(
        function_call: dict,
        context_messages: list,
        session_id: str,
        user_id: str,
) -> str:
    function_name = function_call["name"]

    result = await memory_client.resolve_tool_call(
        tool_call=function_call,
        session_id=session_id,
        namespace=await _get_namespace(user_id),
    )

    if not result["success"]:
        logger.error(f"Function call failed: {result['error']}")
        return result["formatted_response"]

    follow_up_messages = context_messages + [
        {
            "role": "assistant",
            "content": f"Let me {function_name.replace('_', ' ')}...",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "role": "function",
            "name": function_name,
            "content": result["formatted_response"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "role": "user",
            "content": "Please provide a helpful response based on this information.",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]

    final_response = llm.invoke(follow_up_messages)
    response_content = str(final_response.content)

    if not response_content or not response_content.strip():
        if (getattr(final_response, "tool_calls", None) or
            (hasattr(final_response, "additional_kwargs") and "tool_calls" in final_response.additional_kwargs)):
             logger.info(f"Memory tool call {function_name} led to more tool calls.")

        logger.error(
            f"Empty response from LLM in memory tool call handler. Function: {function_name}"
        )
        logger.error(f"Response object: {final_response}")
        logger.error(f"Response content: '{final_response.content}'")
        logger.error(
            f"Response additional_kwargs: {getattr(final_response, 'additional_kwargs', {})}"
        )
        return "I apologize, but I couldn't generate a proper response to your request."

    return response_content

async def _handle_function_call(
        function_call: dict,
        context_messages: list,
        session_id: str,
        user_id: str,
) -> str:
    function_name = function_call["name"]
    logger.info(f"Handling function call: {function_name}")

    if function_name == "web_search":
        return await _handle_web_search_call(function_call)

    return await _handle_memory_tool_call(
        function_call, context_messages, session_id, user_id
    )

async def _generate_response(
        session_id: str,
        user_id: str,
        messages: Optional[list] = None,
        iteration: Optional[int] = 1,
) -> str:
    logger.info(f"Generate: user {user_id}: session {session_id}: iteration {iteration}")
    if not messages:
        working_memory = await _get_working_memory(session_id, user_id)
        context_messages = working_memory.messages
    else:
        logger.info(f"Iteration {iteration} with {len(messages)} messages")
        context_messages = messages

    context_messages_dicts = []
    for msg in context_messages:
        if hasattr(msg, "role") and hasattr(msg, "content"):
            created_at = getattr(msg, "created_at", None)
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            elif created_at is None:
                created_at = datetime.now(timezone.utc).isoformat()
            
            msg_dict = {
                "role": msg.role,
                "content": msg.content,
                "created_at": created_at
            }
            context_messages_dicts.append(msg_dict)
        else:
            context_messages_dicts.append(msg)

    context_messages = [
        msg for msg in context_messages_dicts
    ]

    if iteration == 1:
        context_messages.insert(0, SYSTEM_PROMPT)

    try:
        current_message = context_messages[-1]
        logger.info(f"Role: {current_message.get('role')}")
        if current_message.get('role') == "user":
            logger.info(f"Content: {current_message.get('content')}")

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
                        res = await memory_client.resolve_tool_call(
                            tool_call={
                                "name": fname,
                                "arguments": call.get("function", {}).get(
                                    "arguments", "{}"
                                ),
                            },
                            session_id=session_id,
                            namespace=await _get_namespace(user_id),
                            user_id=user_id,
                        )
                except Exception as e:
                    logger.error(f"Tool '{fname}' failed: {e}")
                    res = {"success": False, "error": str(e)}
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

            return await _generate_response(session_id, user_id, messages, iteration + 1)

        if hasattr(response, "additional_kwargs") and "function_call" in response.additional_kwargs:
            return await _handle_function_call(
                response.additional_kwargs["function_call"],
                context_messages,
                session_id,
                user_id,
            )

        response_content = str(response.content) if response.content is not None else ""

        if not response_content or not response_content.strip():
            logger.error("Empty response from LLM in main response generation")
            logger.error(f"Response object: {response}")
            logger.error(f"Response content: '{response.content}'")
            logger.error(
                f"Response additional_kwargs: {getattr(response, 'additional_kwargs', {})}"
            )
            return "I apologize, but I couldn't generate a proper response to your request."

        return response_content
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return "I'm sorry, I encountered an error processing your request."

async def process_user_input(
        user_input: str,
        session_id: str,
        user_id: str,
) -> str:
    try:
        await _add_message_to_working_memory(
            session_id, user_id, "user", user_input
        )

        response = await _generate_response(
            session_id, user_id
        )

        if not response or not response.strip():
            logger.error("Generated response is empty, using fallback message")
            response = "I'm sorry, I encountered an error generating a response to your request."

        await _add_message_to_working_memory(
            session_id, user_id, "assistant", response
        )

        return response

    except Exception as e:
        logger.exception(f"Error processing user input: {e}")
        return "I'm sorry, I encountered an error processing your request."

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

async def chat_fn(message, _, state, request: gr.Request):
    if not state.get("authenticated", False):
        client_ip = _get_client_ip(request)
        logger.warning(f"Unauthorized access attempt from IP: {client_ip}")
        yield "Unauthorized. Please log in first."
        return

    user_id = state.get("username", "guest")
    session_id = state.get("session_id", "guest")
    reply = await process_user_input(message, session_id, user_id)
    builder = ""

    for ch in reply:
        builder += ch
        yield builder

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
        with gr.Accordion("Session:", open=True):
            session_box_md = gr.Markdown(session_md({}))

    with gr.Row(elem_classes=["chat-window"]):
        with gr.Column(elem_classes=["card"]):
            gr.Markdown("<div class='card-title'>Chat with Assistant</div>")
            gr.ChatInterface(
                fn=chat_fn,
                additional_inputs=[st]
            )
    
    with gr.Row():
        gr.HTML("<div style='flex: 1;'></div>")
        with gr.Column(scale=0, min_width=100):
            logout_button = gr.Button("Logout", variant="secondary", size="sm")
        gr.HTML("<div style='flex: 1;'></div>")

    return session_box_md, logout_button

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
    st = gr.State({"username": "", "ams_url": "", "history": [], "authenticated": False, "session_id": str(uuid.uuid4())})

    with gr.Column(visible=True, elem_id="login-container") as login_box:
        gr.HTML(f"""
            <div style="max-width: 400px; margin: 100px auto; padding: 40px; background: white; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <img src="{LOGO_SRC}" alt="Redis" style="height: 40px; margin: 0 auto 16px; display: block;">
                    <h2 style="font-family: 'Space Grotesk', sans-serif; color: #0b1220; margin: 0; text-align: center;">Redis LangCache Demo</h2>
                    <p style="color: #64748b; margin-top: 8px; text-align: center;">Enter the password to access</p>
                </div>
            </div>
        """)
        with gr.Row():
            gr.HTML("<div style='flex: 1;'></div>")
            with gr.Column(scale=1, min_width=300):
                username_input = gr.Textbox(
                    label="🏷️ Username",
                    type="text",
                    placeholder="Enter your username",
                    elem_id="username-input",
                )
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
        session_box, logout_btn = render_demo()

    # Handle login
    def handle_login(username, password, state, request: gr.Request):
        if password == APP_PASSWORD:
            state["username"] = username
            state["ams_url"] = AGENT_MEMORY_SERVER_URL
            state["authenticated"] = True
            state["session_id"] = str(uuid.uuid4())
            return (
                gr.update(visible=False),
                gr.update(visible=True),
                "",
                state,
                session_md(state),
            )
        else:
            client_ip = _get_client_ip(request)
            logger.warning(f"Failed login attempt from IP: {client_ip}")
            state["authenticated"] = False
            return (
                gr.update(visible=True),
                gr.update(visible=False),
                "<p style='color: #ef4444; text-align: center; margin-top: 10px;'>❌ Incorrect password</p>",
                state,
                gr.update(),
            )

    # Handle logout
    def handle_logout(state):
        state["authenticated"] = False
        state["username"] = ""
        state["ams_url"] = ""
        return (
            gr.update(visible=True),
            gr.update(visible=False),
            "",
            state,
            gr.update(value=session_md(state)),
        )

    login_btn.click(
        fn=handle_login,
        inputs=[username_input, password_input, st],
        outputs=[login_box, main_app, login_status, st, session_box],
        show_progress="hidden",
    )

    password_input.submit(
        fn=handle_login,
        inputs=[username_input, password_input, st],
        outputs=[login_box, main_app, login_status, st, session_box],
        show_progress="hidden",
    )

    logout_btn.click(
        fn=handle_logout,
        inputs=[st],
        outputs=[login_box, main_app, login_status, st, session_box],
        show_progress="hidden",
    )

def main():
    app.launch(css=CUSTOM_CSS)

if __name__ == "__main__":
    main()
