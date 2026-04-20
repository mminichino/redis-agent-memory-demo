"use client";

import type { ChatEvent } from "@/lib/types";
import { MarkdownContent } from "@/components/chat/markdown-content";
import { Card } from "@/components/ui/card";

type ChatThreadProps = {
  events: ChatEvent[];
  isStreaming: boolean;
  /** When true, show full tool call args, tool result payloads, etc. */
  showDebugDetails: boolean;
};

function isToolMessageEvent(event: ChatEvent): boolean {
  return event.type === "message" && (event.role === "tool" || event.role === "function");
}

export function ChatThread({ events, isStreaming, showDebugDetails }: ChatThreadProps) {
  const visibleEvents = showDebugDetails
    ? events
    : events.filter((e) => e.type !== "tool_call" && !isToolMessageEvent(e));

  if (!events.length) {
    return (
      <Card className="p-6">
        <p className="text-sm text-muted">
          Start a conversation to see streamed agent output, tool calls, and runtime events.
        </p>
      </Card>
    );
  }

  if (!visibleEvents.length) {
    return (
      <Card className="p-6">
        <p className="text-sm text-muted">
          Tool calls and raw tool payloads are hidden in the compact view. Enable &quot;Show tool
          responses&quot; in Settings to see full tool messages, arguments, and result bodies.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {visibleEvents.map((event, idx) => (
        <Card key={`${event.type}-${idx}`} className="p-4">
          {event.type === "status" ? (
            <div className="text-sm text-muted [&_.prose]:text-muted">
              <MarkdownContent markdown={event.message} />
            </div>
          ) : null}
          {event.type === "message" ? (
            <div>
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <p className="text-xs uppercase tracking-wide text-muted">{event.role}</p>
                {typeof event.runtime_ms === "number" ? (
                  <p className="text-xs tabular-nums text-muted">
                    {(event.runtime_ms / 1000).toFixed(2)}s elapsed
                  </p>
                ) : null}
              </div>
              <div className="mt-1">
                <MarkdownContent markdown={event.content || ""} />
              </div>
            </div>
          ) : null}
          {event.type === "tool_call" ? (
            <div>
              <p className="text-xs uppercase tracking-wide text-blue-300">Tool call</p>
              <p className="mt-1 text-sm font-medium text-foreground">{event.name}</p>
              <pre className="mt-2 overflow-x-auto rounded-md bg-canvas p-2 text-xs text-muted">
                {event.args}
              </pre>
            </div>
          ) : null}
          {event.type === "tool_result" ? (
            <div>
              <p className="text-xs uppercase tracking-wide text-green-300">Tool result</p>
              <p className="mt-1 text-sm text-foreground">
                <span className="font-medium">{event.name}</span>
                <span className="text-muted"> · </span>
                <span className="tabular-nums text-muted">
                  {(event.runtime_ms / 1000).toFixed(2)}s elapsed
                </span>
              </p>
              {showDebugDetails ? (
                <div className="mt-1 text-muted [&_.prose]:text-muted">
                  <MarkdownContent markdown={event.content} />
                </div>
              ) : null}
            </div>
          ) : null}
          {event.type === "error" ? (
            <p className="text-sm text-red-300">{event.message}</p>
          ) : null}
          {event.type === "done" ? (
            <p className="text-sm text-green-300">Response complete.</p>
          ) : null}
        </Card>
      ))}
      {isStreaming ? <p className="text-xs text-muted">Streaming response...</p> : null}
    </div>
  );
}
