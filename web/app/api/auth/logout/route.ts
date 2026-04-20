import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { clearSessionCookie, SESSION_COOKIE } from "@/lib/auth";
import { deleteSession } from "@/lib/redis";

export async function POST(request: Request) {
  const token = cookies().get(SESSION_COOKIE)?.value ?? "";
  if (token) await deleteSession(token);
  const response = NextResponse.redirect(new URL("/login", request.url));
  clearSessionCookie(response);
  return response;
}
