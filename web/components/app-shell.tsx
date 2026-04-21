import Link from "next/link";
import { AppShellStatus } from "@/components/app-shell-status";
import { LogoutForm } from "@/components/logout-form";
import type { Account } from "@/lib/types";

type AppShellProps = {
  user: Account;
  children: React.ReactNode;
};

export function AppShell({ user, children }: AppShellProps) {
  return (
    <div className="flex h-[100dvh] max-h-[100dvh] flex-col overflow-hidden bg-canvas">
      <header className="sticky top-0 z-50 shrink-0 border-b border-border bg-panel/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 md:px-6">
          <div className="min-w-0 flex-1">
            <p className="text-xs uppercase tracking-wide text-muted">Redis Agent Memory</p>
            <h1 className="text-sm font-semibold text-foreground">
              Chat Operations Console
            </h1>
          </div>
          <AppShellStatus />
          <nav className="flex shrink-0 items-center gap-3">
            <Link
              href="/app"
              className="rounded-md px-3 py-2 text-sm text-foreground transition hover:bg-panelMuted"
            >
              Chat
            </Link>
            <Link
              href="/app/settings"
              className="rounded-md px-3 py-2 text-sm text-foreground transition hover:bg-panelMuted"
            >
              Settings
            </Link>
            <Link
              href="/admin/accounts"
              className="rounded-md px-3 py-2 text-sm text-foreground transition hover:bg-panelMuted"
            >
              Accounts
            </Link>
            <div className="hidden text-right text-xs text-muted md:block">
              <p>{user.first_name || user.user_id}</p>
              <p>{user.user_id}</p>
            </div>
            <LogoutForm />
          </nav>
        </div>
      </header>
      <main className="mx-auto flex min-h-0 w-full max-w-7xl flex-1 flex-col overflow-hidden px-4 py-4 md:px-6">
        {children}
      </main>
    </div>
  );
}
