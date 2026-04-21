import { randomBytes, scryptSync, timingSafeEqual } from "crypto";

const KEY_LENGTH = 64;

export function hashPassword(password: string): string {
  const salt = randomBytes(16).toString("hex");
  const digest = scryptSync(password, salt, KEY_LENGTH).toString("hex");
  return `${salt}:${digest}`;
}

export function verifyPassword(password: string, storedHash: string): boolean {
  const [salt, digestHex] = storedHash.split(":");
  if (!salt || !digestHex) return false;

  const inputDigest = scryptSync(password, salt, KEY_LENGTH);
  const storedDigest = Buffer.from(digestHex, "hex");
  if (inputDigest.length !== storedDigest.length) return false;
  return timingSafeEqual(inputDigest, storedDigest);
}
