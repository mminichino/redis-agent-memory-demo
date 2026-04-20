"use client";

import { useAppShellSessionStatus } from "@/components/chat/chat-health-context";

export function AppShellStatus() {
  const status = useAppShellSessionStatus();
  return (
    <p className="shrink-0 text-sm text-muted">
      <span className="text-foreground/80">Status: </span>
      <span className={status === "healthy" ? "text-green-300" : "text-red-300"}>
        {status === "healthy" ? "Healthy" : "Attention needed"}
      </span>
    </p>
  );
}
