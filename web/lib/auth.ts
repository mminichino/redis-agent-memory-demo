import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { getAccount, getSession } from "@/lib/redis";

export const SESSION_COOKIE = "ramd_session";

export async function getCurrentUser() {
  const token = cookies().get(SESSION_COOKIE)?.value ?? "";
  if (!token) return null;
  const session = await getSession(token);
  if (!session) return null;
  const account = await getAccount(session.user_id);
  if (!account) return null;
  return account;
}

export function clearSessionCookie(response: NextResponse) {
  response.cookies.set(SESSION_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0
  });
}
