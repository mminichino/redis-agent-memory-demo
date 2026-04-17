from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import AsyncIterator

import grpc
import grpc.aio
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, message_to_dict

from memory_demo import chat_service_pb2
from memory_demo import chat_service_pb2_grpc
from memory_demo.driver import ChatWithMemory

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8088


def _base_message_to_json(msg: BaseMessage) -> str:
    return json.dumps(message_to_dict(msg), ensure_ascii=False)


class ChatGrpcServicer(chat_service_pb2_grpc.ChatServiceServicer):
    def __init__(self, chat: ChatWithMemory) -> None:
        self._chat = chat

    async def ProcessInput(
        self,
        request: chat_service_pb2.ProcessInputRequest,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[chat_service_pb2.BaseMessageChunk]:
        try:
            async for msg in self._chat.process_input_async(
                request.content,
                request.session_id,
                request.user_id,
            ):
                if not isinstance(msg, BaseMessage):
                    continue
                yield chat_service_pb2.BaseMessageChunk(
                    message_json=_base_message_to_json(msg)
                )
        except Exception as e:
            logger.exception("ProcessInput failed: %s", e)
            await context.abort(grpc.StatusCode.INTERNAL, str(e))


async def _serve_async(port: int, chat: ChatWithMemory | None = None) -> None:
    load_dotenv()
    ams_url = os.getenv("AGENT_MEMORY_SERVER_URL", "http://localhost:8000")
    namespace = os.getenv("MEMORY_DEMO_NAMESPACE", "demo")
    chat = chat or ChatWithMemory(ams_url=ams_url, namespace=namespace)

    server = grpc.aio.server()
    chat_service_pb2_grpc.add_ChatServiceServicer_to_server(ChatGrpcServicer(chat), server)
    listen = f"[::]:{port}"
    server.add_insecure_port(listen)
    await server.start()
    logger.info("gRPC ChatService listening on %s (AGENT_MEMORY_SERVER_URL=%s)", listen, ams_url)
    try:
        await server.wait_for_termination()
    finally:
        await asyncio.shield(server.stop(None))


def serve(port: int | None = None) -> None:
    p = port if port is not None else int(os.getenv("GRPC_PORT", str(DEFAULT_PORT)))
    asyncio.run(_serve_async(p))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s [%(filename)s:%(lineno)d]",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    serve()


if __name__ == "__main__":
    main()
