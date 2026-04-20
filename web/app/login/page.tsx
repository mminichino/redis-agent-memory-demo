"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { safeJson } from "@/lib/utils";

type LoginError = { error?: string };

export default function LoginPage() {
  const router = useRouter();
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    if (!userId.trim() || !password) {
      setError("Please enter both user ID and password.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId.trim(), password })
      });
      if (!response.ok) {
        const body = await safeJson<LoginError>(response);
        setError(body?.error ?? "Invalid credentials.");
      } else {
        router.push("/app");
        router.refresh();
      }
    } catch {
      setError("Unable to reach auth service.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-md p-6">
        <div className="mb-6">
          <p className="text-xs uppercase tracking-wide text-muted">Secure Access</p>
          <h1 className="mt-1 text-2xl font-semibold text-foreground">
            Sign in to Chat Console
          </h1>
          <p className="mt-2 text-sm text-muted">
            Use your workspace credentials to access memory-backed chat and admin controls.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="user_id" className="mb-1 block text-sm font-medium text-foreground">
              User ID
            </label>
            <Input
              id="user_id"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="admin"
              autoComplete="username"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-foreground">
              Password
            </label>
            <Input
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              placeholder="Enter your password"
              autoComplete="current-password"
            />
          </div>
          {error ? (
            <p className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </p>
          ) : null}
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Signing in..." : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
