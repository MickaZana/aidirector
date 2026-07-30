# Developer Onboarding Notes

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | Next.js 15 (App Router) |
| Language | TypeScript 5.x |
| Styling | Tailwind CSS 4.x |
| State | Zustand 5.x |
| Data Fetching | TanStack React Query 5.x |
| Auth | Clerk |
| Icons | Lucide (via AppIcon wrapper) |
| Animations | Framer Motion 11.x |
| Monitoring | Sentry |
| Testing | Vitest + Testing Library |

## Project Structure

```
apps/web/
├── app/                      # Next.js App Router pages
│   ├── app/                  # Authenticated routes
│   │   ├── upload/           # New Clip (Screen 1)
│   │   ├── processing/       # Processing (Screen 2)
│   │   ├── clips/            # My Clips (Screen 3)
│   │   ├── jobs/             # Pipeline jobs
│   │   ├── director/         # Director review
│   │   └── ...
│   ├── layout.tsx            # Root layout (Clerk, Sentry, Toaster)
│   └── page.tsx              # Marketing landing page
├── components/               # Shared UI components
│   ├── brand/                # Logo, branding
│   ├── error-handling/       # Error boundaries, offline banner
│   └── layout/               # AppShell, Sidebar, TopBar
├── features/                 # Feature modules
│   ├── design-system/        # Component library
│   ├── new-clip/             # Upload flow
│   ├── my-clips/             # Clip gallery
│   ├── feedback/             # Feedback widget
│   ├── onboarding/           # First-run tour
│   └── ...
├── hooks/                    # Shared React hooks
├── services/                 # Application services
│   ├── analytics.ts          # Product analytics
│   ├── upload-service.ts     # File upload orchestration
│   └── ...
├── stores/                   # Zustand stores
│   ├── toast-store.ts        # Toast notifications
│   └── upload-queue.ts       # Upload queue
└── lib/                      # Utilities
    ├── api/                  # API client + types + endpoints
    ├── cn.ts                 # Classname utility (legacy — use DS)
    └── format.ts             # Display formatters
```

## Key Patterns

### 3-Screen Creator Flow

```
Upload (Screen 1) → Processing (Screen 2) → My Clips (Screen 3)
```

Each screen is a full-page experience in `app/app/upload/`, `app/app/processing/`, and `app/app/clips/`.

### Analytics

Product events are tracked via the analytics service:

```ts
import { analytics } from "@/services/analytics";
analytics.track("event_name", { optionalProp: "value" });
```

All event names are in `ANALYTICS_EVENTS` constant. Events are stored in localStorage and can be flushed to a backend endpoint later.

### State Management

- **Toast notifications** → `useToastStore` / `toast` helper
- **Upload queue** → `useUploadStore`
- **Server state** → TanStack React Query (where implemented)

### Error Handling

- **Page errors** → `error.tsx` at route group level
- **API errors** → Custom `ApiError` class + rate-limit/billing-limit DOM events
- **Network status** → `OfflineBanner` + `useOnlineStatus`
- **Pipeline failures** → `PipelineErrorCard`

## Development

### Commands

```bash
npm run dev          # Start dev server
npm run typecheck    # TypeScript check
npm run test         # Run tests
npm run build        # Production build
npm run lint         # Lint check
```

### Before Committing

1. `npm run typecheck` — must pass with 0 errors.
2. `npm run test` — all tests must pass.
3. `npm run build` — must succeed.

## Common Gotchas

1. **Imports** — Always import from the design-system barrel (`@/features/design-system`), not individual component paths.
2. **Icons** — Never import from `lucide-react` directly. Use `<AppIcon name="iconName" />`.
3. **cn utility** — Use `@/features/design-system/utils/cn`, not `@/lib/cn`.
4. **Animations** — Maximum 250ms. Use `motion-safe:` prefix. Use DS animation tokens from `constants/animations.ts`.
5. **"use client"** — Only add when the component uses React hooks, browser APIs, or event handlers. Server components are preferred.
6. **Console logs** — Remove before committing. Use `analytics.track()` for product events.
