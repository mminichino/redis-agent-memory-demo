const env = {
  redisHost: process.env.REDIS_HOST ?? "localhost",
  redisPort: Number(process.env.REDIS_PORT ?? "6379"),
  redisPassword: process.env.REDIS_PASSWORD ?? "",
  adminUser: process.env.ADMIN_USER ?? "admin",
  adminPassword: process.env.ADMIN_PASSWORD ?? "password",
  chatApiUrl: process.env.CHAT_API_URL ?? "http://localhost:8088"
};

export function getEnv() {
  return env;
}
