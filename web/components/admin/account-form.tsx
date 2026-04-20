"use client";

import { useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

const schema = z.object({
  user_id: z.string().min(3, "User ID must be at least 3 characters."),
  first_name: z.string().min(1, "First name is required."),
  last_name: z.string().min(1, "Last name is required."),
  email: z.string().email("Please use a valid email address.").optional().or(z.literal("")),
  password: z.string().min(8, "Password must be at least 8 characters.")
});

type FormState = z.infer<typeof schema>;

type AccountFormProps = {
  onCreated: () => Promise<void>;
};

const defaultState: FormState = {
  user_id: "",
  first_name: "",
  last_name: "",
  email: "",
  password: ""
};

export function AccountForm({ onCreated }: AccountFormProps) {
  const [form, setForm] = useState<FormState>(defaultState);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [status, setStatus] = useState("");
  const [isSubmitting, setSubmitting] = useState(false);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const parsed = schema.safeParse(form);
    if (!parsed.success) {
      const fieldErrors = parsed.error.flatten().fieldErrors;
      setErrors({
        user_id: fieldErrors.user_id?.[0],
        first_name: fieldErrors.first_name?.[0],
        last_name: fieldErrors.last_name?.[0],
        email: fieldErrors.email?.[0],
        password: fieldErrors.password?.[0]
      });
      return;
    }

    setErrors({});
    setStatus("");
    setSubmitting(true);
    try {
      const response = await fetch("/api/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data)
      });
      if (!response.ok) {
        const body = (await response.json()) as { error?: string };
        setStatus(body.error ?? "Unable to create account.");
      } else {
        setStatus("Account saved successfully.");
        setForm(defaultState);
        await onCreated();
      }
    } catch {
      setStatus("Network error while saving account.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="p-4">
      <h2 className="text-base font-semibold text-foreground">Create or update account</h2>
      <p className="mt-1 text-sm text-muted">
        Manage non-admin access for the chat workspace.
      </p>
      <form className="mt-4 grid gap-3 md:grid-cols-2" onSubmit={handleSubmit}>
        <Input
          placeholder="User ID (e.g. analyst_01)"
          value={form.user_id}
          onChange={(e) => update("user_id", e.target.value)}
          error={errors.user_id}
          aria-label="User ID"
        />
        <Input
          placeholder="First name"
          value={form.first_name}
          onChange={(e) => update("first_name", e.target.value)}
          error={errors.first_name}
          aria-label="First name"
        />
        <Input
          placeholder="Last name"
          value={form.last_name}
          onChange={(e) => update("last_name", e.target.value)}
          error={errors.last_name}
          aria-label="Last name"
        />
        <Input
          placeholder="Email (optional)"
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
          error={errors.email}
          aria-label="Email"
        />
        <div className="md:col-span-2">
          <Input
            placeholder="Temporary password"
            type="password"
            value={form.password}
            onChange={(e) => update("password", e.target.value)}
            error={errors.password}
            aria-label="Password"
          />
        </div>
        <div className="md:col-span-2 flex items-center justify-between">
          <p className="text-xs text-muted" aria-live="polite">
            {status}
          </p>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving..." : "Save account"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
