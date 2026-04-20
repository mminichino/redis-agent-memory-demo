# Web Console

Next.js frontend for `src.memory_demo.grpc_chat` with Redis-backed auth and account management.

## Environment variables

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
ADMIN_USER=admin
ADMIN_PASSWORD=password
CHAT_API_URL=http://localhost:8088
```

## Run

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.
