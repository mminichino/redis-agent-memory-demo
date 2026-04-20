import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login", "/api/auth/login"];
const PROTECTED_PAGE_PREFIXES = ["/app", "/admin"];
const PROTECTED_API_PREFIXES = ["/api/chat", "/api/accounts", "/api/auth/session"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Never run auth logic on Next.js internals or static assets — running middleware
  // on these paths can break chunk loading (e.g. app-pages-internals.js 404).
  if (pathname.startsWith("/_next") || pathname === "/favicon.ico") {
    return NextResponse.next();
  }

  const session = request.cookies.get("ramd_session")?.value;

  if (PUBLIC_PATHS.includes(pathname)) {
    return NextResponse.next();
  }

  const requiresAuth =
    PROTECTED_PAGE_PREFIXES.some((prefix) => pathname.startsWith(prefix)) ||
    PROTECTED_API_PREFIXES.some((prefix) => pathname.startsWith(prefix));

  if (requiresAuth && !session) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Unauthorized." }, { status: 401 });
    }
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

// Match Next.js recommendation: skip api + Next internals so RSC/chunks load reliably.
export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"]
};
