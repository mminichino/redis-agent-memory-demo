/**
 * Public origin for redirects behind reverse proxies (for example, Kubernetes ingress).
 * Prefer X-Forwarded-* when present; otherwise use Host / request URL.
 */

function hostnameFromHostHeader(host: string): string {
  if (host.startsWith("[")) {
    const end = host.indexOf("]");
    return end > 1 ? host.slice(1, end) : host;
  }
  const colon = host.indexOf(":");
  return colon === -1 ? host : host.slice(0, colon);
}

function isBindAllHostname(hostname: string): boolean {
  const h = hostname.replace(/^\[|]$/g, "");
  return h === "0.0.0.0" || h === "::";
}

function isBrokenOrigin(origin: string): boolean {
  try {
    return isBindAllHostname(new URL(origin).hostname);
  } catch {
    return true;
  }
}

export function getPublicOrigin(request: Request): string {
  const forwardedHost = request.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const forwardedProto = request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim();

  if (forwardedHost && !isBindAllHostname(hostnameFromHostHeader(forwardedHost))) {
    const proto =
      forwardedProto === "http" || forwardedProto === "https" ? forwardedProto : "https";
    return `${proto}://${forwardedHost}`;
  }

  const hostHeader = request.headers.get("host")?.trim();
  const url = new URL(request.url);
  if (hostHeader && !isBindAllHostname(hostnameFromHostHeader(hostHeader))) {
    const proto =
      forwardedProto === "http" || forwardedProto === "https"
        ? forwardedProto
        : url.protocol.replace(":", "");
    return `${proto}://${hostHeader}`;
  }

  return url.origin;
}

function parseHttpOrigin(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const u = new URL(raw.trim());
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    return u.origin;
  } catch {
    return null;
  }
}

function refererOrigin(referer: string | null): string | null {
  if (!referer) return null;
  try {
    return new URL(referer).origin;
  } catch {
    return null;
  }
}

export function resolveLogoutRedirectOrigin(
  request: Request,
  clientOriginField: string | null | undefined
): string {
  const fromServer = getPublicOrigin(request);
  const client = parseHttpOrigin(clientOriginField);
  const ref = refererOrigin(request.headers.get("referer"));

  if (client && ref && client === ref) {
    return client;
  }

  if (!isBrokenOrigin(fromServer)) {
    return fromServer;
  }

  return fromServer;
}
