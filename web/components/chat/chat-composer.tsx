"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type ChatComposerProps = {
  onSubmit: (prompt: string) => Promise<void>;
  isLoading: boolean;
  className?: string;
};

export function ChatComposer({ onSubmit, isLoading, className }: ChatComposerProps) {
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const value = prompt.trim();
    if (!value) {
      setError("Please enter a message before sending.");
      return;
    }
    setError("");
    await onSubmit(value);
    setPrompt("");
  }

  return (
    <div className={cn("p-4", className)}>
      <form onSubmit={handleSubmit} className="space-y-3">
        <label htmlFor="prompt" className="block text-sm font-medium text-foreground">
          Message
        </label>
        <Input
          id="prompt"
          name="prompt"
          placeholder="Ask the assistant to summarize account activity for this week."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          error={error}
          disabled={isLoading}
          aria-invalid={Boolean(error)}
        />
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted">
            Responses stream in real time from the chat service
          </p>
          <Button type="submit" disabled={isLoading}>
            {isLoading ? "Sending..." : "Send message"}
          </Button>
        </div>
      </form>
    </div>
  );
}
