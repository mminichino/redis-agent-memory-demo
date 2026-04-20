import { redirect } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { UserSettingsForm } from "@/components/settings/user-settings-form";
import { getCurrentUser } from "@/lib/auth";

export default async function UserSettingsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  return (
    <AppShell user={user}>
      <div className="mx-auto w-full max-w-3xl">
        <UserSettingsForm initial={user.settings} />
      </div>
    </AppShell>
  );
}
