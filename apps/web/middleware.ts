import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

// All /app/* and the legacy /dashboard routes require an authenticated user.
const isProtected = createRouteMatcher(["/app(.*)", "/dashboard(.*)"]);

export default clerkMiddleware(async (auth, req) => {
  if (isProtected(req)) await auth.protect();
});

export const config = {
  matcher: [
    "/((?!_next|.*\\..*).*)",
    "/(api|trpc)(.*)",
  ],
};
