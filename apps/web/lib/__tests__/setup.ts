import { vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import React from "react";

// Mock Next.js router
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/app/upload",
  useSearchParams: () => new URLSearchParams(),
  redirect: vi.fn(),
}));

// Mock Clerk
vi.mock("@clerk/nextjs", () => ({
  auth: () => Promise.resolve({ userId: "test_user", orgId: null }),
  currentUser: () => Promise.resolve({ id: "test_user" }),
  useAuth: () => ({ userId: "test_user", orgId: null, isSignedIn: true }),
  useUser: () => ({ user: { id: "test_user" }, isLoaded: true }),
  SignedIn: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
  SignedOut: () => null,
  SignInButton: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
  ClerkProvider: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
  UserButton: () => null,
}));
