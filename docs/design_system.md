# Design System Documentation

## Overview

The AI Director design system lives in `apps/web/features/design-system/`. It provides a consistent set of components, constants, hooks, and utilities used across all features.

## Principles

1. **Single source of truth** — All UI primitives come from the design system.
2. **No inline styling** — Use DS components wherever one exists.
3. **Maximum 250ms animations** — No bounce easings. Tokens in `constants/animations.ts`.
4. **Accessibility-first** — All interactive elements have keyboard support, ARIA labels, and reduced-motion support.

---

## Component Catalog

### Layout Components

| Component | Description |
|-----------|-------------|
| `PageContainer` | Max-width content wrapper with consistent padding |
| `Stack` | Vertical/horizontal flex layout with configurable gap |
| `Section` | Page section with optional title |
| `Card` | Content card with optional hover state and dense variant |

### Typography

| Component | Variants |
|-----------|----------|
| `Typography` | `hero`, `title`, `sectionTitle`, `subtitle`, `small`, `caption` |

Use `Typography` for all visible text. Avoid raw `<p>`, `<h1>`, etc.

### Feedback Components

| Component | Usage |
|-----------|-------|
| `Button` | Primary, secondary, ghost variants with size options |
| `Badge` | Small label for status, category, or count |
| `StatusBadge` | Processing status indicator (success/processing/failed) |
| `PlatformBadge` | Platform label (YouTube Shorts, TikTok, Instagram Reels) |
| `IconButton` | Circular icon-only button |
| `LoadingSpinner` | Generic loading spinner |
| `SkeletonLoader` | Content skeleton placeholder (configurable lines, widths) |
| `EmptyState` | Page empty state with icon, title, description, and optional action |
| `ProgressIndicator` | Circular progress ring with optional percentage |
| `ProgressTimeline` | Linear stage timeline for processing flows |

### Feedback Overlays

| Component | Description |
|-----------|-------------|
| `SuccessToast` | Green notification toast (auto-dismiss) |
| `ErrorToast` | Red notification toast (auto-dismiss) |
| `InfoBanner` | Configurable info/warning/error/success banner |
| `ConfirmationDialog` | Modal dialog for destructive action confirmation |
| `BottomSheet` | Slide-up panel for mobile detail views |

### Icons

All icons use the `AppIcon` component:

```tsx
import { AppIcon } from "@/features/design-system";

<AppIcon name="upload" size="md" />
<AppIcon name="checkCircle" size="lg" className="text-emerald-500" />
```

**Available icon names:** See `ICON_MAP` in `components/AppIcon.tsx`.

**Sizes:** `xs`, `sm`, `md`, `lg`, `xl`, `2xl`, `3xl`.

**Important:** Never import Lucide icons directly. Always use `AppIcon`.

---

## Constants

| Module | Exports |
|--------|---------|
| `constants/colors.ts` | Color tokens |
| `constants/spacing.ts` | Spacing scale |
| `constants/typography.ts` | Type scale |
| `constants/radius.ts` | Border radius scale |
| `constants/shadows.ts` | Shadow tokens |
| `constants/animations.ts` | Duration tokens (fast: 150ms, default: 200ms, slow: 250ms) |

Usage:

```tsx
import { animations, easings } from "@/features/design-system";
// animations.fast === "150ms"
// animations.default === "200ms"
// animations.slow === "250ms"
```

---

## Hooks

| Hook | Description |
|------|-------------|
| `useBreakpoint()` | Returns current responsive breakpoint |

---

## Utilities

| Utility | Description |
|---------|-------------|
| `cn()` | Classname merge (clsx + tailwind-merge). Replaces `@/lib/cn`. |

---

## Barrel Export

All public exports are re-exported from `features/design-system/index.ts`:

```tsx
import {
  Button, Card, Typography, AppIcon, PageContainer, ...
} from "@/features/design-system";
```

Components within `features/` should import from the barrel, not individual component paths.

---

## Adding a New Component

1. Create the component in `features/design-system/components/`.
2. Export it from `features/design-system/index.ts`.
3. Follow existing patterns for TypeScript interfaces, JSDoc, and accessibility.
4. Use only Tailwind classes — no CSS modules or inline styles.
