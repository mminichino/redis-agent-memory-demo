import Redis from "ioredis";
import { randomUUID } from "crypto";
import { getEnv } from "@/lib/env";
import { hashPassword, verifyPassword } from "@/lib/password";
import {
  type Account,
  type Session,
  type UserSettings,
  defaultUserSettings
} from "@/lib/types";

const ACCOUNT_INDEX_KEY = "ramd:accounts:index";
const ACCOUNT_KEY_PREFIX = "ramd:account:";
const SESSION_KEY_PREFIX = "ramd:session:";
const SESSION_TTL_SECONDS = 60 * 60 * 24;

let redisClient: Redis | null = null;
let adminEnsured = false;

function getRedis() {
  if (redisClient) return redisClient;
  const env = getEnv();
  redisClient = new Redis({
    host: env.redisHost,
    port: env.redisPort,
    password: env.redisPassword || undefined,
    lazyConnect: false,
    maxRetriesPerRequest: 2,
    enableReadyCheck: true
  });
  return redisClient;
}

function accountKey(userId: string): string {
  return `${ACCOUNT_KEY_PREFIX}${userId}`;
}

function sessionKey(token: string): string {
  return `${SESSION_KEY_PREFIX}${token}`;
}

function mergeUserSettings(value: unknown): UserSettings {
  if (!value || typeof value !== "object") return { ...defaultUserSettings };
  const o = value as Record<string, unknown>;
  return {
    ...defaultUserSettings,
    ...(typeof o.show_tool_responses === "boolean"
      ? { show_tool_responses: o.show_tool_responses }
      : {})
  };
}

function parseStoredSettings(json: string | undefined): UserSettings {
  if (!json) return { ...defaultUserSettings };
  try {
    return mergeUserSettings(JSON.parse(json) as unknown);
  } catch {
    return { ...defaultUserSettings };
  }
}

function mapAccount(raw: Record<string, string>): Account | null {
  if (!raw || !raw.user_id) return null;
  return {
    user_id: raw.user_id,
    first_name: raw.first_name ?? "",
    last_name: raw.last_name ?? "",
    email: raw.email || undefined,
    is_admin: raw.is_admin === "1",
    created_at: raw.created_at ?? new Date(0).toISOString(),
    updated_at: raw.updated_at ?? new Date(0).toISOString(),
    settings: parseStoredSettings(raw.settings)
  };
}

async function ensureAdminAccount(): Promise<void> {
  if (adminEnsured) return;

  const env = getEnv();
  const now = new Date().toISOString();
  const redis = getRedis();
  const key = accountKey(env.adminUser);

  const existing = await redis.hgetall(key);
  const passwordHash = hashPassword(env.adminPassword);

  await redis.sadd(ACCOUNT_INDEX_KEY, env.adminUser);

  if (!existing.user_id) {
    await redis.hset(key, {
      user_id: env.adminUser,
      first_name: "Admin",
      last_name: "User",
      email: "",
      is_admin: "1",
      password_hash: passwordHash,
      created_at: now,
      updated_at: now
    });
  } else {
    await redis.hset(key, {
      password_hash: passwordHash,
      updated_at: now,
      is_admin: "1"
    });
  }

  adminEnsured = true;
}

export async function initAuthStore(): Promise<void> {
  await ensureAdminAccount();
}

export async function authenticateUser(
  userId: string,
  password: string
): Promise<Account | null> {
  await ensureAdminAccount();
  const redis = getRedis();
  const raw = await redis.hgetall(accountKey(userId));
  if (!raw.user_id || !raw.password_hash) return null;
  if (!verifyPassword(password, raw.password_hash)) return null;
  return mapAccount(raw);
}

export async function createSession(userId: string): Promise<Session> {
  const token = randomUUID();
  const now = new Date().toISOString();
  const redis = getRedis();
  await redis.hset(sessionKey(token), {
    user_id: userId,
    created_at: now
  });
  await redis.expire(sessionKey(token), SESSION_TTL_SECONDS);
  return { token, user_id: userId, created_at: now };
}

export async function getSession(token: string): Promise<Session | null> {
  if (!token) return null;
  await ensureAdminAccount();
  const redis = getRedis();
  const raw = await redis.hgetall(sessionKey(token));
  if (!raw.user_id) return null;
  await redis.expire(sessionKey(token), SESSION_TTL_SECONDS);
  return {
    token,
    user_id: raw.user_id,
    created_at: raw.created_at ?? new Date(0).toISOString()
  };
}

export async function deleteSession(token: string): Promise<void> {
  if (!token) return;
  const redis = getRedis();
  await redis.del(sessionKey(token));
}

export async function getAccount(userId: string): Promise<Account | null> {
  await ensureAdminAccount();
  const redis = getRedis();
  const raw = await redis.hgetall(accountKey(userId));
  return mapAccount(raw);
}

export async function isAdminUser(userId: string): Promise<boolean> {
  const account = await getAccount(userId);
  return Boolean(account?.is_admin);
}

export async function listAccounts(): Promise<Account[]> {
  await ensureAdminAccount();
  const env = getEnv();
  const redis = getRedis();
  const ids = await redis.smembers(ACCOUNT_INDEX_KEY);
  const all = await Promise.all(ids.map((id) => getAccount(id)));
  return all
    .filter((item): item is Account => Boolean(item))
    .filter((item) => item.user_id !== env.adminUser)
    .sort((a, b) => a.user_id.localeCompare(b.user_id));
}

type UpsertInput = {
  user_id: string;
  first_name: string;
  last_name: string;
  email?: string;
  password?: string;
};

export async function upsertAccount(input: UpsertInput): Promise<Account> {
  await ensureAdminAccount();
  const redis = getRedis();
  const now = new Date().toISOString();
  const key = accountKey(input.user_id);
  const existing = await redis.hgetall(key);

  const payload: Record<string, string> = {
    user_id: input.user_id,
    first_name: input.first_name,
    last_name: input.last_name,
    email: input.email ?? "",
    is_admin: "0",
    updated_at: now
  };
  if (!existing.created_at) payload.created_at = now;
  if (input.password) payload.password_hash = hashPassword(input.password);

  await redis.sadd(ACCOUNT_INDEX_KEY, input.user_id);
  await redis.hset(key, payload);

  const account = await getAccount(input.user_id);
  if (!account) {
    throw new Error("Failed to upsert account");
  }
  return account;
}

export async function deleteAccount(userId: string): Promise<void> {
  await ensureAdminAccount();
  const redis = getRedis();
  await redis.del(accountKey(userId));
  await redis.srem(ACCOUNT_INDEX_KEY, userId);
}

export async function updateUserSettings(
  userId: string,
  partial: Partial<UserSettings>
): Promise<UserSettings> {
  await ensureAdminAccount();
  const account = await getAccount(userId);
  if (!account) {
    throw new Error("Account not found");
  }
  const next: UserSettings = { ...account.settings, ...partial };
  const redis = getRedis();
  const now = new Date().toISOString();
  await redis.hset(accountKey(userId), {
    settings: JSON.stringify(next),
    updated_at: now
  });
  return next;
}
