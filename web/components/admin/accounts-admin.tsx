"use client";

import { useCallback, useEffect, useState } from "react";
import { AccountForm } from "@/components/admin/account-form";
import { AccountsTable } from "@/components/admin/accounts-table";
import type { Account } from "@/lib/types";
import { Card } from "@/components/ui/card";

type AccountsResponse = {
  accounts: Account[];
};

export function AccountsAdmin() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/accounts");
      if (!response.ok) {
        throw new Error("Unable to load account list.");
      }
      const data = (await response.json()) as AccountsResponse;
      setAccounts(data.accounts);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);

  async function handleDelete(userId: string) {
    setError("");
    setLoading(true);
    try {
      const response = await fetch(`/api/accounts/${encodeURIComponent(userId)}`, {
        method: "DELETE"
      });
      if (!response.ok) {
        throw new Error("Unable to delete account.");
      }
      await loadAccounts();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unexpected error");
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto space-y-4">
      <Card className="p-4">
        <h2 className="text-lg font-semibold text-foreground">Account administration</h2>
        <p className="mt-1 text-sm text-muted">
          Create and manage non-admin users with access to the workspace.
        </p>
      </Card>
      <AccountForm onCreated={loadAccounts} />
      {error ? (
        <Card className="border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </Card>
      ) : null}
      <AccountsTable accounts={accounts} onDelete={handleDelete} isLoading={loading} />
    </div>
  );
}
