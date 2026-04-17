from __future__ import annotations
import asyncio
import json
import os
import time
import logging
import traceback
import textwrap

from dateutil.parser import ParserError
from jinja2 import Template
from dateutil import parser as date_parser
from typing import Any, AsyncGenerator, Generator, Optional, Sequence
from datetime import datetime, timezone
from dotenv import load_dotenv
from agent_memory_client import MemoryAPIClient, MemoryClientConfig
from agent_memory_client.models import WorkingMemory, MemoryRecord, MemoryMessage, ClientMemoryRecord, MemoryTypeEnum
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage, SystemMessage, HumanMessage, ToolCall
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

SYSTEM_PROMPT = """
You are a helpful assistant with access to web search and memory tools.

## Primary goal
Answer the user's question clearly and directly.

## Tool-use policy
- Use `web_search` for current, live, recent, or time-sensitive information if the tool is available.
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
"""

GET_DATE_PROMPT = """
You are an agent that analyzes chat messages to see if they reference a point in time.
- The current date and time is: {{current_datetime}}
- Look for a specific occurrence or experience: something that happened, an action someone took, a visit, trip, meeting, conversation, or any event-like utterance.
- If the message contains a specific calendar date or time, extract it.
- If the message contains a relative date, convert it to an absolute date based on the current date and time.
    - For example: 
    - "I went to the park yesterday." would have yesterday's date.
    - "We had a meeting last week on Tuesday." would be the date of Tuesday of last week.
- Provide the date and time in ISO 8601 format.
- Do not include any explanations or justifications.
- Do not include any markdown or other text or characters.
- Just return the datetime string in ISO format.
- If there isn't a date or time, return "None".
"""

CLASSIFY_MESSAGE_PROMPT = """
You are an agent that classifies chat messages before they are stored in memory.

Classify each message as **semantic**, **episodic**, or **message**:

- **semantic**: Durable, general information: preferences, identity, standing traits, facts stated as timeless/general knowledge, or opinions not tied to one specific occurrence.
- **episodic**: A specific occurrence or experience: something that happened, an action someone took, a visit, trip, meeting, conversation, or any event-like utterance.
- **message**: A message that is not semantic or episodic.

- Provide only the message type as "episodic", "semantic" or "message"
- Do not include any explanations or justifications.
- Do not include any markdown or other text or characters.
"""

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


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, MemoryRecord):
            return obj.model_dump()
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


class ChatWithMemory:
    def __init__(
            self,
            smart_model: str = "gpt-5.2-chat-latest",
            fast_model: str = "gpt-4o",
            ams_url: str = "http://localhost:8000",
            namespace: str = "default",
            *,
            smart_chat_model: BaseChatModel | None = None,
    ):
        self.error_count = 0
        self.smart_model = smart_model
        self.fast_model = fast_model
        self.ams_url = ams_url
        self.namespace = namespace

        if "TAVILY_API_KEY" in os.environ:
            available_functions = [web_search_function]
            logger.info("Tavily key present. Web search enabled.")
        else:
            available_functions = []
            logger.info("Tavily key not present. Web search disabled.")

        memory_client_config = MemoryClientConfig(
            base_url=self.ams_url
        )
        self.memory_client = MemoryAPIClient(memory_client_config)
        memory_tool_schemas = MemoryAPIClient.get_all_memory_tool_schemas()
        for tool_schema in memory_tool_schemas:
            available_functions.append(tool_schema["function"])

        logger.info(
            f"Available memory tools: {[tool['function']['name'] for tool in memory_tool_schemas]}"
        )

        base_smart = smart_chat_model or ChatOpenAI(model=self.smart_model)
        self.smart_llm = base_smart.bind_tools(available_functions)
        self.fast_llm = ChatOpenAI(model=self.fast_model)

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def increment_error_count(self) -> None:
        self.error_count += 1
        tb_text = traceback.format_exc()
        logger.error(tb_text)

    def _get_namespace(self, user_id: str) -> str:
        return f"{self.namespace}:{user_id}"

    def _scoped_tool_arguments(self, function_name: str, arguments: str | dict[str, Any], user_id: str) -> str:
        try:
            if isinstance(arguments, dict):
                args = dict(arguments)
            else:
                args = json.loads(arguments) if arguments and str(arguments).strip() else {}
        except (json.JSONDecodeError, TypeError):
            self.increment_error_count()
            return arguments if isinstance(arguments, str) else json.dumps(arguments or {})
        if function_name == "search_memory" and user_id:
            args["user_id"] = user_id
        return json.dumps(args)

    @staticmethod
    def _assistant_content_str(msg: Any) -> str:
        c = getattr(msg, "content", msg)
        if isinstance(c, str):
            return c.strip()
        if isinstance(c, list):
            parts: list[str] = []
            for block in c:
                if isinstance(block, str):
                    parts.append(block.strip())
                elif isinstance(block, dict) and "text" in block:
                    parts.append(str(block["text"]).strip())
                else:
                    parts.append(str(block).strip())
            return "".join(parts)
        return str(c).strip() if c is not None else ""

    @staticmethod
    def normalize_messages(messages: Sequence[dict | BaseMessage]) -> list[BaseMessage]:
        out: list[BaseMessage] = []
        for m in messages:
            if isinstance(m, dict):
                role = m.get("role")
                content = m.get("content", "")
                if role == "system":
                    out.append(SystemMessage(content=content))
                elif role == "user":
                    out.append(HumanMessage(content=content))
                elif role == "assistant":
                    tc = m.get("tool_calls")
                    if tc:
                        first = tc[0] if tc else None
                        if isinstance(first, dict) and first.get("type") == "function" and "function" in first:
                            lc_tc = ChatWithMemory._openai_tool_blocks_to_lc(tc)
                        else:
                            lc_tc = tc
                        out.append(AIMessage(content=content or "", tool_calls=lc_tc))
                    else:
                        out.append(AIMessage(content=content))
                elif role == "tool":
                    out.append(
                        ToolMessage(
                            content=content if isinstance(content, str) else str(content),
                            tool_call_id=m.get("tool_call_id", ""),
                            name=m.get("name") or "",
                        )
                    )
            else:
                out.append(m)
        return out

    @staticmethod
    def _openai_tool_blocks_to_lc(blocks: Sequence[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for i, block in enumerate(blocks):
            if not isinstance(block, dict):
                continue
            if block.get("name") and "args" in block:
                args = block["args"]
                normalized.append(
                    {
                        "name": block["name"],
                        "args": args if isinstance(args, dict) else ChatWithMemory._tool_call_args_as_dict(args),
                        "id": block.get("id", f"tool_call_{i}"),
                        "type": block.get("type", "tool_call"),
                    }
                )
                continue
            if block.get("type") == "function" and "function" in block:
                fn = block["function"]
                name = fn.get("name", "")
                arg_raw = fn.get("arguments", "{}")
                try:
                    args = json.loads(arg_raw) if isinstance(arg_raw, str) else (arg_raw or {})
                except json.JSONDecodeError:
                    args = {}
                normalized.append(
                    {
                        "name": name,
                        "args": args,
                        "id": block.get("id", f"tool_call_{i}"),
                        "type": "tool_call",
                    }
                )
        return normalized

    @staticmethod
    def _tool_calls_from_ai_message(message: AIMessage) -> list[ToolCall] | list[dict[str, Any]]:
        if message.tool_calls:
            return list(message.tool_calls)
        raw = (message.additional_kwargs or {}).get("tool_calls") or []
        return ChatWithMemory._openai_tool_blocks_to_lc(raw)

    @staticmethod
    def _tool_call_args_as_dict(args: Any) -> dict[str, Any]:
        if isinstance(args, dict):
            return args
        if isinstance(args, str):
            try:
                return json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                return {}
        return {}

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def query_fast_llm(self, context: str, message: str) -> AIMessage:
        logger.info(f"query fast llm:\n{textwrap.indent(message, '  ')}")
        messages = [
            SystemMessage(content=context),
            HumanMessage(content=message)
        ]
        response = self.fast_llm.invoke(messages)
        return response

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def query_smart_llm(self, context: str, messages: list[dict | BaseMessage]) -> AIMessage:
        if len(messages) > 0 and isinstance(messages[0], SystemMessage):
            messages = messages[1:]
        for m in messages:
            if isinstance(m, HumanMessage):
                logger.info(f"smart llm message:\n{textwrap.indent(self._assistant_content_str(m.content), '  ')}")
        message_list: list[BaseMessage] = [
            SystemMessage(content=context)
        ]
        message_list.extend(self.normalize_messages(messages))
        response = self.smart_llm.invoke(message_list)
        return response

    async def get_working_memory(self, session_id: str, user_id: str) -> WorkingMemory:
        logger.info(f"Get working memory: {user_id} ({session_id})")
        created, result = await self.memory_client.get_or_create_working_memory(
            session_id=session_id,
            user_id=user_id,
            namespace=self._get_namespace(user_id),
            model_name=self.smart_model,
        )
        return WorkingMemory(**result.model_dump())

    async def add_message_to_working_memory(
            self,
            session_id: str,
            user_id: str,
            role: str,
            content: str,
            timestamp: datetime,
    ):
        logger.info(f"Add to working memory: {user_id} ({session_id}) {role}")
        new_message = MemoryMessage(
            role=role,
            content=content,
            created_at=timestamp
        )
        await self.memory_client.append_messages_to_working_memory(
            session_id=session_id,
            messages=[new_message],
            namespace=self._get_namespace(user_id),
            user_id=user_id,
            model_name=self.smart_model,
        )

    async def add_message_to_long_term_memory(
            self,
            session_id: str,
            user_id: str,
            content: str,
            memory_type_enum: MemoryTypeEnum,
            timestamp: datetime,
            event_date: Optional[datetime] = None
    ):
        logger.info(f"Add to long term memory: {user_id} ({session_id}) "
                    f"type: {memory_type_enum.value} event date: {event_date or 'None'}")
        memory_record = ClientMemoryRecord(
            user_id=user_id,
            session_id=session_id,
            namespace=self._get_namespace(user_id),
            text=content,
            memory_type=memory_type_enum,
            created_at=timestamp,
            event_date=event_date,
        )
        return await self.memory_client.create_long_term_memory(
            memories=[memory_record]
        )

    async def long_term_memory_async(
            self,
            session_id: str,
            user_id: str,
            content: str,
            timestamp: datetime,
    ):
        template = Template(GET_DATE_PROMPT)
        date_prompt = template.render(
            current_datetime=datetime.now(timezone.utc).isoformat()
        )
        response = self.query_fast_llm(date_prompt, content)
        date_response = self._assistant_content_str(response.content)
        logger.debug(f"long_term_memory: date response: {date_response}")
        try:
            event_date = date_parser.parse(date_response)
        except ParserError:
            event_date = None

        response = self.query_fast_llm(CLASSIFY_MESSAGE_PROMPT, content)
        type_response = self._assistant_content_str(response.content)
        logger.debug(f"long_term_memory: type response: {type_response}")
        message_type: MemoryTypeEnum
        if type_response == "episodic":
            message_type = MemoryTypeEnum.EPISODIC
        elif type_response == "semantic":
            message_type = MemoryTypeEnum.SEMANTIC
        else:
            message_type = MemoryTypeEnum.MESSAGE

        return await self.add_message_to_long_term_memory(
            session_id,
            user_id,
            content,
            message_type,
            timestamp,
            event_date,
        )

    def long_term_memory(
            self,
            session_id: str,
            user_id: str,
            content: str,
            timestamp: datetime,
    ):
        return self.loop.run_until_complete(
            self.long_term_memory_async(
                session_id,
                user_id,
                content,
                timestamp,
            )
        )

    async def _search_web(self, query: str) -> str:
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
            self.increment_error_count()
            logger.error(f"Error performing web search: {e}")
            return f"Error performing web search: {str(e)}"

    async def _generate_response(
            self,
            session_id: str,
            user_id: str,
            context_messages: Sequence[dict | BaseMessage],
            timestamp: datetime,
            message: Optional[str] = None,
            iteration: Optional[int] = 1,
    ) -> AsyncGenerator[BaseMessage]:
        logger.info(f"Generate: {user_id} ({session_id}) iteration {iteration} with {len(context_messages)} messages")
        try:
            conversation: list[BaseMessage] = self.normalize_messages(list(context_messages))
            if message is not None:
                conversation.append(HumanMessage(content=message))
                await self.add_message_to_working_memory(
                    session_id, user_id, "user", message, timestamp
                )

            response = self.query_smart_llm(SYSTEM_PROMPT, conversation)
            tool_calls = self._tool_calls_from_ai_message(response)
            logger.debug(f"Tools to call:\n{json.dumps(tool_calls, indent=2)}")

            if tool_calls:
                tool_messages: list[ToolMessage] = []
                for tc in tool_calls:
                    fname = tc.get("name") or ""
                    args = self._tool_call_args_as_dict(tc.get("args"))
                    tc_id = tc.get("id") or f"tool_call_{len(tool_messages)}"
                    start_time = time.time()

                    try:
                        logger.info(f"Calling tool: {fname}")
                        if fname == "web_search":
                            res_content = await self._search_web(args.get("query", ""))
                            res = {
                                "success": True,
                                "function_name": fname,
                                "result": res_content,
                                "formatted_response": res_content,
                            }
                        else:
                            res = await self.memory_client.resolve_tool_call(
                                tool_call={
                                    "name": fname,
                                    "arguments": self._scoped_tool_arguments(fname, args, user_id),
                                },
                                session_id=session_id,
                                namespace=self._get_namespace(user_id),
                                user_id=user_id,
                            )
                    except Exception as e:
                        self.increment_error_count()
                        logger.error(f"Tool '{fname}' failed: {e}")
                        raise

                    execution_time_s = time.time() - start_time
                    if not res.get("success", False):
                        self.increment_error_count()
                        tool_content = f"Error calling tool '{fname}': {res.get('error')}"
                        tool_status = "error"
                    else:
                        payload = res.get("result")
                        try:
                            tool_content = (
                                json.dumps(payload, cls=CustomEncoder)
                                if isinstance(payload, (dict, list))
                                else str(res.get("formatted_response", ""))
                            )
                        except Exception as e:
                            self.increment_error_count()
                            logger.error(f"Error serializing payload: {e}")
                            raise
                        tool_status = "success"

                    tm = ToolMessage(
                        content=tool_content,
                        tool_call_id=tc_id,
                        name=fname,
                        status=tool_status,
                        response_metadata={"execution_time_seconds": execution_time_s},
                    )
                    tool_messages.append(tm)
                    logger.info(f"Tool {res.get('function_name', fname)} success: {res.get('success', False)}")
                    logger.debug(f"Tool result:\n{json.dumps(res, cls=CustomEncoder, indent=2)}")
                    yield tm

                next_messages = list(conversation) + [response] + tool_messages
                nxt = iteration + 1 if iteration else 1
                async for resp in self._generate_response(
                    session_id, user_id, next_messages, timestamp, message=None, iteration=nxt
                ):
                    yield resp
            elif response.content is not None:
                text = self._assistant_content_str(response)
                await self.add_message_to_working_memory(
                    session_id, user_id, "assistant", text, timestamp
                )
                yield AIMessage(
                    content=text,
                )
        except Exception as e:
            self.increment_error_count()
            logger.error(f"Error generating response: {e}", exc_info=True)
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def process_input_async(
            self,
            content: str,
            session_id: str,
            user_id: str,
            timestamp: Optional[datetime] = None,
    ) -> AsyncGenerator[BaseMessage]:
        logger.info(f"Process user input: user {user_id}: session {session_id}: message {content}")
        try:
            if timestamp is None:
                message_timestamp = datetime.now(timezone.utc)
            else:
                message_timestamp = timestamp

            working_memory = await self.get_working_memory(session_id, user_id)
            context_messages: list[dict[str, str]] = [msg.model_dump(include={'role', 'content'}) for msg in working_memory.messages]

            async for message in self._generate_response(
                    session_id, user_id, context_messages, message_timestamp, content
            ):
                if not message:
                    continue
                logger.info(f"Answer: {message.content}")
                yield message
        except Exception as e:
            self.increment_error_count()
            logger.exception(f"Error processing user input: {e}")
            yield AIMessage(
                content="I'm sorry, I encountered an error processing your request."
            )

    def process_input(
        self,
        user_input: str,
        session_id: str,
        user_id: str,
        timestamp: Optional[datetime] = None,
    ) -> Generator[BaseMessage]:
        agen = self.process_input_async(user_input, session_id, user_id, timestamp)
        try:
            while True:
                try:
                    msg = self.loop.run_until_complete(agen.__anext__())
                except StopAsyncIteration:
                    break
                yield msg
        finally:
            self.loop.run_until_complete(agen.aclose())
