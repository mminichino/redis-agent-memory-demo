import { randomUUID } from "crypto";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { ChatWorkspace } from "@/components/chat/chat-workspace";
import { getCurrentUser } from "@/lib/auth";

export default async function AppPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const sessionId = randomUUID();

  return (
    <AppShell user={user}>
      <ChatWorkspace
        userId={user.user_id}
        sessionId={sessionId}
        showToolResponses={user.settings.show_tool_responses}
      />
    </AppShell>
  );
}
