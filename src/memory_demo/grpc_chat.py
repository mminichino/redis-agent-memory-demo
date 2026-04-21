from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import AsyncIterator

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s [%(filename)s:%(lineno)d]",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

import grpc
import grpc.aio
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, message_to_dict

from memory_demo import chat_service_pb2
from memory_demo import chat_service_pb2_grpc
from memory_demo.driver import ChatWithMemory

logger = logging.getLogger()

DEFAULT_PORT = 8088


def _base_message_to_json(msg: BaseMessage) -> str:
    return json.dumps(message_to_dict(msg), ensure_ascii=False)


class ChatGrpcServicer(chat_service_pb2_grpc.ChatServiceServicer):
    def __init__(self, chat: ChatWithMemory) -> None:
        self._chat = chat

    async def ProcessInput(
        self,
        request: chat_service_pb2.ProcessInputRequest, # noqa
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[chat_service_pb2.BaseMessageChunk]: # noqa
        try:
            logger.info(f"ProcessInput: user: {request.user_id} session: {request.session_id}")
            async for msg in self._chat.process_input_async(
                request.content,
                request.session_id,
                request.user_id,
            ):
                if not isinstance(msg, BaseMessage):
                    continue
                yield chat_service_pb2.BaseMessageChunk( # noqa
                    message_json=_base_message_to_json(msg)
                )
        except Exception as e:
            logger.error(f"ProcessInput failed: {e}")
            await context.abort(grpc.StatusCode.INTERNAL, str(e))


async def serve(port: int, chat: ChatWithMemory | None = None) -> None:
    load_dotenv()
    ams_url = os.getenv("AGENT_MEMORY_SERVER_URL", "http://localhost:8000")
    namespace = os.getenv("MEMORY_DEMO_NAMESPACE", "demo")
    chat: ChatWithMemory = chat or ChatWithMemory(ams_url=ams_url, namespace=namespace, enable_sync_methods=False)

    server = grpc.aio.server()
    chat_service_pb2_grpc.add_ChatServiceServicer_to_server(ChatGrpcServicer(chat), server)
    listen = f"[::]:{port}"
    server.add_insecure_port(listen)
    await server.start()
    logger.info(f"gRPC ChatService listening on {listen} (AGENT_MEMORY_SERVER_URL={ams_url})")
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("gRPC ChatService terminated by user")
        await server.stop(0)


def main() -> None:
    p = int(os.getenv("GRPC_PORT", str(DEFAULT_PORT)))
    asyncio.run(serve(p))


if __name__ == "__main__":
    main()
