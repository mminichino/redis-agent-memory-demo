from __future__ import annotations

import json
import logging
import os
import sys
from typing import Iterator

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s [%(filename)s:%(lineno)d]",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

import grpc
from concurrent import futures
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

    def ProcessInput(
        self,
        request: chat_service_pb2.ProcessInputRequest,
        context: grpc.aio.ServicerContext,
    ) -> Iterator[chat_service_pb2.BaseMessageChunk]:
        try:
            logger.info(f"ProcessInput: user: {request.user_id} session: {request.session_id}")
            for msg in self._chat.process_input(
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
            logger.error(f"ProcessInput failed: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))


def serve(port: int, chat: ChatWithMemory | None = None) -> None:
    load_dotenv()
    ams_url = os.getenv("AGENT_MEMORY_SERVER_URL", "http://localhost:8000")
    namespace = os.getenv("MEMORY_DEMO_NAMESPACE", "demo")
    chat: ChatWithMemory = chat or ChatWithMemory(ams_url=ams_url, namespace=namespace)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
    chat_service_pb2_grpc.add_ChatServiceServicer_to_server(ChatGrpcServicer(chat), server)
    listen = f"[::]:{port}"
    server.add_insecure_port(listen)
    server.start()
    logger.info(f"gRPC ChatService listening on {listen} (AGENT_MEMORY_SERVER_URL={ams_url})")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("gRPC ChatService terminated by user")
        server.stop(0)


def main() -> None:
    p = int(os.getenv("GRPC_PORT", str(DEFAULT_PORT)))
    serve(p)


if __name__ == "__main__":
    main()
