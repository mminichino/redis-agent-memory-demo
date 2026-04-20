"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { UserSettings } from "@/lib/types";

type UserSettingsFormProps = {
  initial: UserSettings;
};

export function UserSettingsForm({ initial }: UserSettingsFormProps) {
  const router = useRouter();
  const [showToolResponses, setShowToolResponses] = useState(initial.show_tool_responses);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setShowToolResponses(initial.show_tool_responses);
  }, [initial.show_tool_responses]);

  async function onSave() {
    setError(null);
    setSaving(true);
    try {
      const response = await fetch("/api/user/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ show_tool_responses: showToolResponses })
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as { error?: string };
        setError(data.error || "Failed to save settings.");
        return;
      }
      router.refresh();
    } catch {
      setError("Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-foreground">User preferences</h2>
        <p className="mt-1 text-sm text-muted">Stored with your account in Redis. More options can be added here over time.</p>
      </div>
      <Card className="p-4">
        <fieldset>
          <legend className="text-sm font-medium text-foreground">Chat</legend>
          <label className="mt-3 flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-border text-brand focus:ring-2 focus:ring-brand/40"
              checked={showToolResponses}
              onChange={(e) => setShowToolResponses(e.target.checked)}
            />
            Show tool responses
          </label>
          <p className="mt-2 text-xs text-muted">
            When enabled, tool calls, arguments, and raw tool messages appear in the chat thread.
          </p>
        </fieldset>
      </Card>
      {error && <p className="text-sm text-red-300">{error}</p>}
      <Button onClick={() => void onSave()} disabled={saving} type="button">
        {saving ? "Saving…" : "Save settings"}
      </Button>
    </div>
  );
}
