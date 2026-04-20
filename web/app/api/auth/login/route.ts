import { NextResponse } from "next/server";
import { z } from "zod";
import { SESSION_COOKIE } from "@/lib/auth";
import { authenticateUser, createSession, initAuthStore } from "@/lib/redis";

const schema = z.object({
  user_id: z.string().min(1),
  password: z.string().min(1)
});

export async function POST(request: Request) {
  await initAuthStore();
  const body = await request.json().catch(() => null);
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid login payload." }, { status: 400 });
  }

  const account = await authenticateUser(parsed.data.user_id, parsed.data.password);
  if (!account) {
    return NextResponse.json({ error: "Invalid credentials." }, { status: 401 });
  }

  const session = await createSession(account.user_id);
  const response = NextResponse.json({ ok: true, user: account });
  response.cookies.set(SESSION_COOKIE, session.token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24
  });
  return response;
}
