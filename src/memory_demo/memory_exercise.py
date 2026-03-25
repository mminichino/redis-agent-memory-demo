import asyncio
import uuid
import typer
import logging
import random
import redis.asyncio as redis
from langchain_openai import ChatOpenAI
from memory_demo.memory_demo import process_user_input, OPENAI_MODEL
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Dict, Any
import memory_demo.memory_demo as m

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer()

llm = ChatOpenAI(model=OPENAI_MODEL)

async def generate_message(history) -> str:
    message_types = [
        "set a durable preference or stable trait (e.g., 'I love drinking green tea', 'I prefer traveling by train')",
        "provide a scheduled event or an important episodic fact (e.g., 'I'm traveling to the Swiss Alps next week departing on Monday', 'I went to the Italian Dolomites last year')",
    ]
    selected_type = random.choice(message_types)
    
    prompt = f"""Generate a single short sentence or question from a user to an AI assistant. 
    The message should {selected_type}. Do not include any other text or quotes. Try not to repeat the same message."""

    prompt_messages = history + [HumanMessage(content=prompt)]
    response = await llm.ainvoke(prompt_messages)
    synthetic_message = response.content.strip()
    history.append(HumanMessage(content=synthetic_message))
    return synthetic_message

async def run_exercise(user_count: int, question_count: int):
    iterations = user_count * question_count
    error_count = 0
    for i in range(1, user_count + 1):
        user_id = f"user{i}"
        
        def get_new_session_id():
            return str(uuid.uuid4())
            
        session_id = get_new_session_id()
        messages_until_session_change = random.randint(2, 5)
        message_counter = 0
        history = [SystemMessage(content="You are a helpful assistant.")]
        
        typer.echo(f"\n--- Processing for {user_id} ---")
        
        for _ in range(question_count):
            if message_counter >= messages_until_session_change:
                session_id = get_new_session_id()
                typer.echo(f"\n--- Session ID changed to {session_id} ---")
                messages_until_session_change = random.randint(2, 5)
            
            question = await generate_message(history)

            typer.echo(f"User (Session: {session_id}): {question}")
            async for response in process_user_input(question, session_id, user_id):
                if not response:
                    error_count += 1
                    continue
                typer.echo(f"Assistant: {response.content}")

            typer.echo("-" * 20)
            message_counter += 1
            progress = (i - 1) * question_count + message_counter
            percentage = progress / iterations
            typer.echo(f"Progress: {percentage:.0%} User: {i} ({message_counter} of {question_count})")
            typer.echo("-" * 20)
    
    typer.echo(f"Generator error count: {error_count}")
    typer.echo(f"Module error count: {m.ERROR_COUNT}")

async def get_redis_memory_stats(redis_url: str) -> Dict[str, Any]:
    client = redis.from_url(redis_url)

    try:
        dbsize = await client.dbsize()
        info = await client.info("memory")
        total_memory_used = info.get("used_memory", 0)

        async def pattern_stats(pattern: str) -> tuple[int, int]:
            count = 0
            total_memory = 0
            async for key in client.scan_iter(match=pattern, count=1000):
                count += 1
                usage = await client.memory_usage(key)
                if usage is not None:
                    total_memory += usage
            return count, total_memory

        async def memory_idx_hash_vector_stats() -> Dict[str, Any]:
            def _to_str(value: Any) -> str:
                if isinstance(value, bytes):
                    return value.decode("utf-8", errors="replace")
                return str(value)

            total_hash_count = 0
            total_hash_bytes = 0
            with_vector_count = 0
            with_vector_bytes = 0
            without_vector_count = 0
            without_vector_bytes = 0

            async for key in client.scan_iter(match="memory_idx:*", count=1000):
                key_type = _to_str(await client.type(key)).lower()
                if key_type != "hash":
                    continue

                total_hash_count += 1
                usage = await client.memory_usage(key)
                key_usage = int(usage or 0)
                total_hash_bytes += key_usage

                has_vector = await client.hexists(key, "vector")
                if has_vector:
                    with_vector_count += 1
                    with_vector_bytes += key_usage
                else:
                    without_vector_count += 1
                    without_vector_bytes += key_usage

            count_divisor = total_hash_count or 1
            bytes_divisor = total_hash_bytes or 1

            return {
                "memory_idx_hash_total_count": total_hash_count,
                "memory_idx_hash_total_bytes": total_hash_bytes,
                "memory_idx_hash_with_vector_count": with_vector_count,
                "memory_idx_hash_with_vector_bytes": with_vector_bytes,
                "memory_idx_hash_with_vector_count_pct": (with_vector_count / count_divisor) * 100,
                "memory_idx_hash_with_vector_bytes_pct": (with_vector_bytes / bytes_divisor) * 100,
                "memory_idx_hash_without_vector_count": without_vector_count,
                "memory_idx_hash_without_vector_bytes": without_vector_bytes,
                "memory_idx_hash_without_vector_count_pct": (without_vector_count / count_divisor) * 100,
                "memory_idx_hash_without_vector_bytes_pct": (without_vector_bytes / bytes_divisor) * 100,
            }

        (
            (memory_idx_count, memory_idx_usage),
            (working_memory_count, working_memory_usage),
            memory_idx_vector_stats,
        ) = await asyncio.gather(
            pattern_stats("memory_idx:*"),
            pattern_stats("working_memory:demo_agent:*"),
            memory_idx_hash_vector_stats(),
        )

        return {
            "total_key_count": dbsize,
            "total_memory_used_bytes": total_memory_used,
            "memory_idx_key_count": memory_idx_count,
            "memory_idx_bytes": memory_idx_usage,
            "working_memory_key_count": working_memory_count,
            "working_memory_bytes": working_memory_usage,
            **memory_idx_vector_stats,
        }
    finally:
        await client.aclose()

@app.command()
def main(
    users: int = typer.Option(1, help="Number of users to process"),
    questions: int = typer.Option(100, help="Number of questions to ask per user"),
    summary: bool = typer.Option(False, help="Print summary of memory usage"),
    redis_url: str = typer.Option("redis://localhost:6379", help="Redis URL")
):
    if summary:
        typer.echo("Summary of Redis Memory Usage:")
        stats = asyncio.run(get_redis_memory_stats(redis_url))
        for key, value in stats.items():
            typer.echo(f"{key}: {value}")
        return

    typer.echo(f"Running Dynamic Memory Exercise with {users} users and {questions} questions each")
    if questions < 1:
        typer.echo("Error: questions parameter must be at least 1")
        raise typer.Exit(code=1)
    asyncio.run(run_exercise(users, questions))

if __name__ == "__main__":
    app()
