import { NextResponse } from "next/server";
import { z } from "zod";
import { getCurrentUser } from "@/lib/auth";
import { streamChat } from "@/lib/grpc-chat";

const schema = z.object({
  content: z.string().min(1),
  session_id: z.string().min(1),
  user_id: z.string().min(1)
});

type LangChainMessage = {
  type?: string;
  data?: {
    content?: unknown;
    name?: string;
    additional_kwargs?: {
      tool_calls?: Array<{
        function?: { name?: string; arguments?: string };
      }>;
    };
  };
};

function serializeSse(payload: object): string {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

function toText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) return content.map((item) => JSON.stringify(item)).join("\n");
  if (content == null) return "";
  return JSON.stringify(content);
}

export async function POST(request: Request) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized." }, { status: 401 });
  }

  const body = await request.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid chat payload." }, { status: 400 });
  }

  if (parsed.data.user_id !== user.user_id) {
    return NextResponse.json({ error: "User mismatch." }, { status: 403 });
  }

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      function emit(payload: object) {
        controller.enqueue(encoder.encode(serializeSse(payload)));
      }

      emit({ type: "status", message: "Connected to chat service." });

      /** Anchor for “elapsed” on the next assistant message, tool result, or system parse error. */
      let segmentStart = Date.now();

      function consumeSegmentMs(): number {
        const now = Date.now();
        const ms = Math.max(0, now - segmentStart);
        segmentStart = now;
        return ms;
      }

      const call = streamChat(parsed.data);
      call.on("data", (chunk) => {
        let parsedMsg: LangChainMessage | null = null;
        try {
          parsedMsg = JSON.parse(chunk.message_json) as LangChainMessage;
        } catch {
          emit({
            type: "message",
            role: "system",
            content: chunk.message_json,
            raw: chunk.message_json,
            runtime_ms: consumeSegmentMs()
          });
          return;
        }

        const role = parsedMsg.type ?? "assistant";
        const content = toText(parsedMsg.data?.content);

        if (role === "tool") {
          const name = parsedMsg.data?.name ?? "tool";
          // Raw tool payload (often hidden in UI) — do not consume segment; wait for tool_result.
          emit({
            type: "message",
            role: "tool",
            content,
            raw: parsedMsg
          });
          emit({
            type: "tool_result",
            name,
            runtime_ms: consumeSegmentMs(),
            content
          });
          return;
        }

        emit({
          type: "message",
          role,
          content,
          raw: parsedMsg,
          runtime_ms: consumeSegmentMs()
        });

        const toolCalls = parsedMsg.data?.additional_kwargs?.tool_calls ?? [];
        for (const toolCall of toolCalls) {
          const name = toolCall.function?.name ?? "unknown_tool";
          emit({
            type: "tool_call",
            name,
            args: toolCall.function?.arguments ?? "{}",
            started_at: Date.now()
          });
        }
      });

      call.on("error", (error) => {
        controller.enqueue(
          encoder.encode(
            serializeSse({
              type: "error",
              message: error.message || "gRPC stream error."
            })
          )
        );
        controller.close();
      });

      call.on("end", () => {
        controller.enqueue(encoder.encode(serializeSse({ type: "done" })));
        controller.close();
      });
    }
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive"
    }
  });
}
