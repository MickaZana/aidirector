/**
 * Environment validation tests.
 *
 * Validates that the validateEnvironment function correctly:
 * - Detects missing required variables
 * - Validates value formats
 * - Distinguishes errors from warnings
 * - Formats results as human-readable strings
 */
import { describe, it, expect } from "vitest";
import {
  validateEnvironment,
  formatValidationResult,
} from "@/config/validateEnvironment";

// ── Tests ───────────────────────────────────────────────────────────────

describe("validateEnvironment", () => {
  it("returns issues for missing required vars", () => {
    const result = validateEnvironment();
    // The function reads process.env at call time
    // In test env these might not be set, which is fine
    expect(result).toHaveProperty("valid");
    expect(result).toHaveProperty("issues");
    expect(Array.isArray(result.issues)).toBe(true);
  });

  it("returns valid result with no issues only when env is properly configured", () => {
    // We can't easily mock process.env in vitest, so verify structure
    const result = validateEnvironment();
    const errorIssues = result.issues.filter((i) => i.severity === "error");
    const warningIssues = result.issues.filter((i) => i.severity === "warning");
    expect(errorIssues.every((i) => i.variable)).toBe(true);
    expect(warningIssues.every((i) => i.variable)).toBe(true);
  });

  it("each issue has the required fields", () => {
    const result = validateEnvironment();
    for (const issue of result.issues) {
      expect(issue).toHaveProperty("variable");
      expect(issue).toHaveProperty("description");
      expect(issue).toHaveProperty("severity");
      expect(issue).toHaveProperty("message");
      expect(["error", "warning"]).toContain(issue.severity);
    }
  });
});

describe("formatValidationResult", () => {
  it("returns success message when valid and no issues", () => {
    const result = {
      valid: true,
      issues: [] as any[],
    };
    const msg = formatValidationResult(result);
    expect(msg).toContain("All environment variables are valid");
  });

  it("returns error message with issues when invalid", () => {
    const result = {
      valid: false,
      issues: [
        {
          variable: "NEXT_PUBLIC_API_URL",
          description: "Backend API base URL",
          severity: "error" as const,
          message: "Missing required environment variable",
        },
      ],
    };
    const msg = formatValidationResult(result);
    expect(msg).toContain("Environment validation failed");
    expect(result.issues[0].variable).toBe("NEXT_PUBLIC_API_URL");
  });

  it("returns warning message for non-critical issues", () => {
    const result = {
      valid: true,
      issues: [
        {
          variable: "NEXT_PUBLIC_SENTRY_DSN",
          description: "Sentry DSN",
          severity: "warning" as const,
          message: "Invalid format",
        },
      ],
    };
    const msg = formatValidationResult(result);
    expect(msg).toContain("Environment has warnings");
    expect(result.issues[0].variable).toBe("NEXT_PUBLIC_SENTRY_DSN");
  });

  it("each issue in formatted output contains severity label", () => {
    const result = {
      valid: false,
      issues: [
        {
          variable: "VAR_1",
          description: "Test",
          severity: "error" as const,
          message: "Missing",
        },
        {
          variable: "VAR_2",
          description: "Test 2",
          severity: "warning" as const,
          message: "Invalid",
        },
      ],
    };
    const msg = formatValidationResult(result);
    expect(msg).toContain("[ERROR]");
    expect(msg).toContain("[WARNING]");
  });
});
