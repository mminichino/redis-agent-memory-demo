import json
import os
import uuid
import gradio as gr
import re
from dotenv import load_dotenv
from pathlib import Path
from agent_memory_client import MemoryAPIClient, MemoryClientConfig
from agent_memory_client.models import WorkingMemory, ClientMemoryRecord, MemoryTypeEnum
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from memory_demo import __version__ as app_version
from functools import partial
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
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2-chat-latest")
CHAT_A_URL = os.getenv("CHAT_A_URL", "http://localhost:8000")
CHAT_B_URL = os.getenv("CHAT_B_URL", "http://localhost:8000")
SESSION_ID = str(uuid.uuid4())
USER_ID = "demo"

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
    - When using **lazily_create_long_term_memory**, ensure you provide the **text** parameter with the content you want to store and the **memory_type** (episodic or semantic).

    Be helpful, friendly, and responsive. Mirror their conversational style - if they're just chatting, chat back. If they ask for help, then help.
    """,
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

memory_client_config_a = MemoryClientConfig(
    base_url=CHAT_A_URL
)
memory_client_config_b = MemoryClientConfig(
    base_url=CHAT_B_URL
)
memory_client_a = MemoryAPIClient(memory_client_config_a)
memory_client_b = MemoryAPIClient(memory_client_config_b)
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

async def _extract_preferences(messages: list) -> list[str]:
    extraction_prompt = [
        {"role": "system", "content": "You are a helpful assistant that extracts personal user preferences from a conversation. "
                                     "Provide a list of concise strings representing the user's preferences, "
                                     "such as 'User likes coffee', 'User prefers dark mode', etc. "
                                     "If no preferences are found, return an empty list. "
                                     "Return the result as a JSON array of strings."},
        {"role": "user", "content": f"Extract preferences from these messages: {json.dumps(messages)}"}
    ]
    try:
        response = llm.invoke(extraction_prompt)
        content = str(response.content)

        match = re.search(r"\[.*]", content, re.DOTALL)
        if match:
            preferences = json.loads(match.group(0))
            if isinstance(preferences, list):
                return [str(p) for p in preferences]
    except Exception as e:
        logger.error(f"Error extracting preferences: {e}")
    return []

async def _get_memory_client(scenario: str) -> MemoryAPIClient:
    if scenario == "A":
        return memory_client_a
    elif scenario == "B":
        return memory_client_b
    else:
        raise ValueError(f"Unknown scenario: {scenario}")

async def _get_namespace(user_id: str) -> str:
    return f"demo_agent:{user_id}"

async def _get_working_memory(session_id: str, user_id: str, scenario: str) -> WorkingMemory:
    memory_client = await _get_memory_client(scenario)
    created, result = await memory_client.get_or_create_working_memory(
        session_id=session_id,
        namespace=await _get_namespace(user_id),
        model_name="gpt-5.2-chat-latest",
    )
    return WorkingMemory(**result.model_dump())

async def _add_message_to_working_memory(session_id: str, user_id: str, role: str, content: str, scenario: str):
    memory_client = await _get_memory_client(scenario)
    new_message = [{"role": role, "content": content}]
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

async def _handle_web_search_call(function_call: dict, context_messages: list) -> str:
    logger.info("Searching the web")
    try:
        function_args = json.loads(function_call["arguments"])
        query = function_args.get("query", "")
        search_results = await _search_web(query)

        follow_up_messages = context_messages + [
            {
                "role": "assistant",
                "content": f"I'll search for that information: {query}",
            },
            {
                "role": "function",
                "name": "web_search",
                "content": search_results,
            },
            {
                "role": "user",
                "content": "Please provide a helpful response based on the search results.",
            },
        ]

        final_response = llm.invoke(follow_up_messages)
        response_content = str(final_response.content)

        if not response_content or not response_content.strip():
            if (getattr(final_response, "tool_calls", None) or
                (hasattr(final_response, "additional_kwargs") and "tool_calls" in final_response.additional_kwargs)):
                logger.info("Web search result led to more tool calls, but handling in simple handler is limited.")
            
            logger.error("Empty response from LLM in web search call handler")
            return "I apologize, but I couldn't generate a response after the web search."

        return response_content

    except (json.JSONDecodeError, TypeError):
        logger.error(f"Invalid web search arguments: {function_call}")
        return "I'm sorry, I encountered an error processing your web search request. Please try again."

async def _handle_memory_tool_call(
        function_call: dict,
        context_messages: list,
        session_id: str,
        user_id: str,
        scenario: str,
) -> str:
    memory_client = await _get_memory_client(scenario)
    function_name = function_call["name"]

    print("Accessing memory...")
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
        },
        {
            "role": "function",
            "name": function_name,
            "content": result["formatted_response"],
        },
        {
            "role": "user",
            "content": "Please provide a helpful response based on this information.",
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
        scenario: str,
) -> str:
    function_name = function_call["name"]

    if function_name == "web_search":
        return await _handle_web_search_call(function_call, context_messages)

    return await _handle_memory_tool_call(
        function_call, context_messages, session_id, user_id, scenario
    )

async def _generate_response(
        session_id: str,
        user_id: str,
        scenario: str,
) -> str:
    memory_client = await _get_memory_client(scenario)
    working_memory = await _get_working_memory(session_id, user_id, scenario)
    context_messages = working_memory.messages

    context_messages_dicts = []
    for msg in context_messages:
        if hasattr(msg, "role") and hasattr(msg, "content"):
            msg_dict = {"role": msg.role, "content": msg.content}
            context_messages_dicts.append(msg_dict)
        else:
            context_messages_dicts.append(msg)

    context_messages = [
        msg for msg in context_messages_dicts if msg.get("role") != "system"
    ]
    context_messages.insert(0, SYSTEM_PROMPT)

    try:
        logger.info(f"Context messages: {context_messages}")
        response = llm.invoke(context_messages)

        tool_calls = getattr(response, "tool_calls", [])
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
                            "arguments", tc.get("arguments", {})
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
            for call in normalized_calls:
                fname = call.get("function", {}).get("name", "")
                try:
                    if fname == "web_search":
                        args = json.loads(call.get("function", {}).get("arguments", "{}"))
                        res_content = await _search_web(args.get("query", ""))
                        res = {"success": True, "result": res_content, "formatted_response": res_content}
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

            assistant_tools_msg = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": normalized_calls,
            }

            tool_messages: list[dict] = []
            for i, (tc, res) in enumerate(results):
                if not res.get("success", False):
                    content = f"Error calling tool '{tc.get('function', {}).get('name', '')}': {res.get('error')}"
                else:
                    payload = res.get("result")
                    try:
                        content = (
                            json.dumps(payload)
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
                    }
                )

            messages = (
                    context_messages + [assistant_tools_msg] + tool_messages
            )
            followup = llm.invoke(messages)
            rounds = 0
            max_rounds = 1
            while (
                    rounds < max_rounds
                    and (getattr(followup, "tool_calls", None) or
                         (hasattr(followup, "additional_kwargs") and "tool_calls" in followup.additional_kwargs))
            ):
                rounds += 1
                follow_calls = getattr(followup, "tool_calls", [])
                if not follow_calls and hasattr(followup, "additional_kwargs"):
                    follow_calls = followup.additional_kwargs.get("tool_calls", [])

                follow_results = []
                for _j, fcall in enumerate(follow_calls):
                    if isinstance(fcall, dict):
                        fname = fcall.get("function", {}).get("name", fcall.get("name", ""))
                        fargs = fcall.get("function", {}).get("arguments", fcall.get("arguments", fcall.get("args", {})))
                        fid = fcall.get("id", f"tool_call_follow_{_j}")
                    else:
                        fname = getattr(fcall, "name", "")
                        fargs = getattr(fcall, "args", {})
                        fid = getattr(fcall, "id", f"tool_call_follow_{_j}")

                    try:
                        if fname == "web_search":
                            if isinstance(fargs, str):
                                try:
                                    fargs = json.loads(fargs)
                                except json.JSONDecodeError:
                                    fargs = {}
                            res_content = await _search_web(fargs.get("query", ""))
                            fres = {"success": True, "result": res_content, "formatted_response": res_content}
                        else:
                            fres = await memory_client.resolve_tool_call(
                                tool_call={"name": fname, "arguments": json.dumps(fargs) if not isinstance(fargs, str) else fargs},
                                session_id=session_id,
                                namespace=await _get_namespace(user_id),
                                user_id=user_id,
                            )
                    except Exception as e:
                        logger.error(
                            f"Follow-up tool '{fname}' failed: {e}"
                        )
                        fres = {"success": False, "error": str(e)}
                    follow_results.append((fcall, fres, fid, fname, fargs))

                norm_follow = []
                for idx2, (fc, fr, fid, fname, fargs) in enumerate(follow_results):
                    if not isinstance(fargs, str):
                        try:
                            fargs_str = json.dumps(fargs)
                        except Exception as e:
                            logger.error(f"Error serializing args: {e}")
                            fargs_str = "{}"
                    else:
                        fargs_str = fargs

                    norm_follow.append(
                        {
                            "id": fid,
                            "type": "function",
                            "function": {
                                "name": fname,
                                "arguments": fargs_str,
                            },
                        }
                    )

                messages.append(
                    {
                        "role": "assistant",
                        "content": followup.content or "",
                        "tool_calls": norm_follow,
                    }
                )
                for k, (fc, fr, fid, fname, fargs) in enumerate(follow_results):
                    if not fr.get("success", False):
                        content = f"Error calling follow-up tool '{fname}': {fr.get('error')}"
                    else:
                        payload = fr.get("result")
                        try:
                            content = (
                                json.dumps(payload)
                                if isinstance(payload, (dict, list))
                                else str(fr.get("formatted_response", ""))
                            )
                        except Exception as e:
                            logger.error(f"Error serializing payload: {e}")
                            content = str(fr.get("formatted_response", ""))
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": fid,
                            "name": fname,
                            "content": content,
                        }
                    )
                followup = llm.invoke(messages)

            return str(followup.content)

        if hasattr(response, "additional_kwargs") and "function_call" in response.additional_kwargs:
            return await _handle_function_call(
                response.additional_kwargs["function_call"],
                context_messages,
                session_id,
                user_id,
                scenario,
            )

        response_content = str(response.content)

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
        scenario: str,
) -> str:
    memory_client = await _get_memory_client(scenario)
    try:
        await _add_message_to_working_memory(
            session_id, user_id, "user", user_input, scenario
        )

        response = await _generate_response(
            session_id, user_id, scenario
        )

        if not response or not response.strip():
            logger.error("Generated response is empty, using fallback message")
            response = "I'm sorry, I encountered an error generating a response to your request."

        await _add_message_to_working_memory(
            session_id, user_id, "assistant", response, scenario
        )

        try:
            working_memory = await _get_working_memory(session_id, user_id, scenario)
            preferences = await _extract_preferences(
                [{"role": msg.role, "content": msg.content} for msg in working_memory.messages]
            )
            if preferences:
                logger.info(f"Extracted preferences: {preferences}")
                memories = [
                    ClientMemoryRecord(
                        text=pref,
                        user_id=user_id,
                        namespace=await _get_namespace(user_id),
                        memory_type=MemoryTypeEnum.SEMANTIC
                    )
                    for pref in preferences
                ]
                await memory_client.create_long_term_memory(memories)
                logger.info(f"Stored {len(memories)} preferences in long-term memory")
        except Exception as e:
            logger.error(f"Error storing preferences: {e}")

        return response

    except Exception as e:
        logger.exception(f"Error processing user input: {e}")
        return "I'm sorry, I encountered an error processing your request."

async def chat_fn(message, _, scenario):
    logger.info(f"Received message from chat: {scenario}")
    reply = await process_user_input(message, SESSION_ID, USER_ID, scenario)
    builder = ""

    for ch in reply:
        builder += ch
        yield builder

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
        chat_a = partial(chat_fn, scenario="A")
        with gr.Column(elem_classes=["card"]):
            gr.Markdown("<div class='card-title'>Chat 🅰️</div>")
            gr.ChatInterface(
                fn=chat_a
            )

        # --- Scenario B ---
        chat_b = partial(chat_fn, scenario="B")
        with gr.Column(elem_classes=["card"]):
            gr.Markdown("<div class='card-title'>Chat 🅱️</div>")
            gr.ChatInterface(
                fn=chat_b
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
