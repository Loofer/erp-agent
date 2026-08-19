# Frontend Agent Guide

## Project Overview

The frontend is a single-page chat application that communicates with the
`motorparts-agent` backend. Users can start new sessions, browse history,
and receive streaming AI responses via Server-Sent Events (SSE).

It is built with **Vue 3** (Composition API), **Vite**, and
**Ant Design Vue** + **Ant Design X Vue** (chat-specific UI components).

---

## Tech Stack

| Layer | Library / Version |
|---|---|
| UI framework | Vue 3 (`^3.5`) |
| Build tool | Vite 8 |
| Language | TypeScript 6 |
| Component library | Ant Design Vue 4 + Ant Design X Vue 1.6 |
| Icons | `@ant-design/icons-vue` |
| State management | Pinia 4 |
| Router | Vue Router 4 |
| Package manager | **pnpm** |

---

## Directory Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── chat.ts          # All HTTP/SSE calls to the backend; type definitions
│   ├── stores/
│   │   └── chat.ts          # Pinia store — messages, sessions, sendMessage()
│   ├── views/
│   │   └── ChatView.vue     # Main chat page (Bubble + Conversations + Sender)
│   ├── components/
│   │   ├── MessageBubble.vue       # Markdown-safe user/assistant messages
│   │   ├── ToolCallSteps.vue       # Tool and routing timeline
│   │   ├── InterruptCard.vue       # Input/approval interruption details
│   │   ├── HitlApprovalBar.vue     # Approve/reject controls
│   │   └── analysis/ChartCard.vue  # Validated chart rendering
│   ├── router/
│   │   └── index.ts         # Vue Router config
│   ├── assets/              # Static assets (images, SVG)
│   ├── style.css            # Global styles
│   ├── auto-imports.d.ts    # Generated — do not edit manually
│   ├── components.d.ts      # Generated — do not edit manually
│   └── main.ts              # App entry point
├── public/                  # Copied verbatim to dist/
│   ├── favicon.svg
│   └── icons.svg
├── index.html
├── vite.config.ts
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── tsconfig.app.json
└── tsconfig.node.json
```

---

## Development Commands

```bash
# Install dependencies
pnpm install

# Start dev server (http://localhost:5173)
pnpm dev

# Type-check + build for production
pnpm build

# Preview production build locally
pnpm preview
```

The dev server proxies `/api` requests to `http://localhost:8000` (the backend).
Start the backend before running the frontend in development.

---

## Auto-Imports

Two Vite plugins handle imports automatically — **do not import these manually**:

- **`unplugin-auto-import`**: `ref`, `computed`, `watch`, `onMounted`, and all
  other Vue 3 composables; `useRouter`, `useRoute`; `defineStore`, `storeToRefs`.
  Type declarations land in `src/auto-imports.d.ts` (generated, committed).

- **`unplugin-vue-components`** + `AntDesignVueResolver`: All `ant-design-vue`
  and `ant-design-x-vue` components are auto-resolved by PascalCase name.
  Type declarations land in `src/components.d.ts` (generated, committed).

If you add a new composable package and want it auto-imported, add it to the
`imports` array in `vite.config.ts`.

---

## Path Alias

`@` is an alias for `src/`. Always use `@/` for absolute imports inside `src/`.

```ts
import { useChatStore } from '@/stores/chat'
import type { ChatMessage } from '@/api/chat'
```

---

## State Management: `stores/chat.ts`

The single Pinia store `useChatStore` owns all chat state:

| State | Type | Description |
|---|---|---|
| `messages` | `ChatMessage[]` | Messages in the active session |
| `sessions` | `SessionItem[]` | Sidebar session list |
| `currentThreadId` | `string \| null` | Active LangGraph thread ID |
| `loading` | `boolean` | `true` while streaming |
| `pendingInterrupt` | `InterruptData \| null` | Current input or approval HITL pause |

Key actions:

| Action | Description |
|---|---|
| `sendMessage(content)` | Pushes user message, opens SSE stream, appends assistant chunks |
| `loadSessions()` | Fetches all threads for the current user via `GET /api/history` |
| `selectSession(threadId)` | Switches to a thread and loads its messages |
| `newSession()` | Resets state to start a blank session |
| `deleteSession(threadId)` | Deletes a session and resets the active thread when needed |

`sendMessage` appends a placeholder assistant bubble (`loading: true`) immediately,
then fills `content` incrementally as SSE `message_chunk` events arrive.

---

## API Layer: `src/api/chat.ts`

All backend communication lives here. Key exports:

### JWT Authorization
The API client sends `Authorization: Bearer <token>` on every chat request. In
development, `VITE_DEV_JWT` can override the bundled temporary token, whose
claims are `sub` and `username`. Replace it with a real login-issued signed JWT
before production; do not put `user_id` in API bodies or query strings.

### `streamChat(message, threadId, callbacks)`

Sends `POST /api/chat/stream` and reads the SSE response manually (no EventSource API —
uses `fetch` + `ReadableStream` for full control). Callbacks:

```ts
{
  onSession(threadId: string): void        // fires once, on first SSE event
  onChunk(chunk: string): void             // fires for each text fragment
  onDone(): void                           // stream finished cleanly
  onError(err: Error): void                // stream finished with error
}
```

### SSE Event Types

| Event | Payload | Handled? |
|---|---|---|
| `session` | `{ thread_id }` | ✅ sets `currentThreadId` |
| `message_chunk` | `{ content }` | ✅ appends text to assistant bubble |
| `complete` | `{ thread_id }` | ✅ calls `onDone` |
| `error` | `{ error }` | ✅ calls `onError` |
| `interrupt` | `{ thread_id, ... }` | ✅ renders input or approval controls |

`content` in `message_chunk` may be a `string` **or** a `ContentBlock[]` array
(LangGraph multimodal format). The parser handles both.

### `fetchHistory()` / `fetchThreadMessages(threadId)`

Thin wrappers around `GET /api/history` and `GET /api/chat/{id}/messages`.
Both return empty arrays on any error (fail-safe, no throws).

---

## UI Components

`ChatView.vue` composes three Ant Design X Vue components:

| Component | Role |
|---|---|
| `<Conversations>` | Left sidebar component — session list with "New chat" button |
| `<Bubble>` | Individual message bubble (user / assistant) |
| `<Sender>` | Bottom input area with send button |

Ant Design icons (`RobotOutlined`, `UserOutlined`, `PlusOutlined`) are used for
avatars and action buttons — import from `@ant-design/icons-vue`.

---

## Routing

`src/router/index.ts` — currently a single route:
- `/` → `ChatView.vue`

Add new pages as additional routes here. Use `<RouterView>` in `App.vue`.

---

## Build Output

`pnpm build` outputs to `frontend/dist/`. The `dist/` directory is gitignored.
For deployment, serve `dist/` as static files behind the same origin as the
backend, or configure a reverse proxy so `/api` routes hit the backend.

---

## Key Conventions

- **Composition API only** — no Options API. Use `<script setup>` in all SFCs.
- **TypeScript strict** — avoid `any`; use the types exported from `@/api/chat.ts`.
- **No manual component imports** — rely on the auto-import plugins.
- **No manual composable imports** — `ref`, `computed`, etc. are globally available.
- **pnpm only** — do not use `npm` or `yarn`; the lockfile is `pnpm-lock.yaml`.
- **`@` alias** — always use `@/` for src-relative imports.
- **Store access** — call `useChatStore()` inside `<script setup>` or composables; do not call it at module scope.

---

## Uncertainties / Suggestions

- **Authentication**: the bundled JWT is a development fixture only. Before
  production, replace it with a login flow that stores and refreshes a signed
  access token.

- **HITL interrupt UI**: Input and approval interruptions are implemented by
  `InterruptCard.vue`, `HitlApprovalBar.vue`, and the store's
  `resumeInput`/`resumeApprove`/`resumeReject` actions. Keep the payload aligned
  with the backend `Command(resume=...)` contract when changing either side.

- **Error UX**: API errors display a raw "请求失败：…" string in the chat bubble.
  Consider a dedicated error state / toast notification.

- **Session deletion**: `ChatView.vue` confirms deletion through its session
  menu. The backend removes the event log plus all LangGraph checkpoints for
  the thread, including child-agent checkpoint namespaces.

- **Message pagination**: `fetchThreadMessages` returns all messages for a thread.
  For long sessions, add a `limit` / `cursor` parameter and lazy-load older
  messages as the user scrolls up.

- **`dist/` and `node_modules/`** are gitignored via `frontend/.gitignore`.
  The `.claude/` local session directory is also gitignored there.
