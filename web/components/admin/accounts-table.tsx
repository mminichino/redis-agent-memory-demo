"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { Account } from "@/lib/types";

type AccountsTableProps = {
  accounts: Account[];
  onDelete: (userId: string) => Promise<void>;
  isLoading: boolean;
};

export function AccountsTable({ accounts, onDelete, isLoading }: AccountsTableProps) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-base font-semibold text-foreground">Accounts</h2>
        <p className="text-sm text-muted">
          Active users that can access chat and memory workflows.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-panelMuted text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-3">User ID</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Updated</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {accounts.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-muted" colSpan={5}>
                  No managed accounts yet.
                </td>
              </tr>
            ) : (
              accounts.map((account) => (
                <tr key={account.user_id} className="hover:bg-panelMuted/50">
                  <td className="px-4 py-3 font-medium text-foreground">{account.user_id}</td>
                  <td className="px-4 py-3 text-foreground">
                    {account.first_name} {account.last_name}
                  </td>
                  <td className="px-4 py-3 text-muted">{account.email || "Not provided"}</td>
                  <td className="px-4 py-3 text-muted">
                    {new Date(account.updated_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="danger"
                      disabled={isLoading}
                      onClick={() => onDelete(account.user_id)}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
