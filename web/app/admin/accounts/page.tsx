import { redirect } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { AccountsAdmin } from "@/components/admin/accounts-admin";
import { getCurrentUser } from "@/lib/auth";

export default async function AdminAccountsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (!user.is_admin) redirect("/app");

  return (
    <AppShell user={user}>
      <AccountsAdmin />
    </AppShell>
  );
}
