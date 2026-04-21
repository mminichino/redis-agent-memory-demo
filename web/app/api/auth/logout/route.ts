import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { clearSessionCookie, SESSION_COOKIE } from "@/lib/auth";
import { resolveLogoutRedirectOrigin } from "@/lib/public-origin";
import { deleteSession } from "@/lib/redis";

export async function POST(request: Request) {
  const token = cookies().get(SESSION_COOKIE)?.value ?? "";
  if (token) await deleteSession(token);

  const form = await request.formData().catch(() => null);
  const clientOriginRaw = form?.get("client_origin");
  const clientOrigin = typeof clientOriginRaw === "string" ? clientOriginRaw : undefined;

  const origin = resolveLogoutRedirectOrigin(request, clientOrigin);
  const response = NextResponse.redirect(new URL("/login", origin));
  clearSessionCookie(response);
  return response;
}
