import { NextResponse } from "next/server";
import { z } from "zod";
import { getCurrentUser } from "@/lib/auth";
import { getEnv } from "@/lib/env";
import { listAccounts, upsertAccount } from "@/lib/redis";

const createSchema = z.object({
  user_id: z.string().min(3),
  first_name: z.string().min(1),
  last_name: z.string().min(1),
  email: z.string().email().optional().or(z.literal("")),
  password: z.string().min(8)
});

async function ensureAdmin() {
  const user = await getCurrentUser();
  if (!user) return { ok: false as const, status: 401 };
  if (!user.is_admin) return { ok: false as const, status: 403 };
  return { ok: true as const };
}

export async function GET() {
  const auth = await ensureAdmin();
  if (!auth.ok) {
    return NextResponse.json({ error: "Unauthorized." }, { status: auth.status });
  }
  const accounts = await listAccounts();
  return NextResponse.json({ accounts });
}

export async function POST(request: Request) {
  const auth = await ensureAdmin();
  if (!auth.ok) {
    return NextResponse.json({ error: "Unauthorized." }, { status: auth.status });
  }
  const body = await request.json().catch(() => null);
  const parsed = createSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid account payload." }, { status: 400 });
  }
  if (parsed.data.user_id === getEnv().adminUser) {
    return NextResponse.json(
      { error: "Admin account is managed by environment configuration." },
      { status: 400 }
    );
  }
  const account = await upsertAccount(parsed.data);
  return NextResponse.json({ account }, { status: 201 });
}
