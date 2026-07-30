/**
 * Environment variable validation.
 *
 * Called once at application startup (in layout.tsx or middleware) to
 * verify that all required environment variables are present and valid.
 * Provides friendly error messages instead of cryptic runtime failures.
 */

export interface EnvRequirement {
  /** Environment variable name */
  variable: string;
  /** Human-readable description of what this variable is for */
  description: string;
  /** Whether the variable is strictly required */
  required: boolean;
  /** Optional validation function */
  validate?: (value: string) => boolean;
}

const REQUIREMENTS: EnvRequirement[] = [
  // ── Frontend-critical ───────────────────────────────────────────────
  {
    variable: "NEXT_PUBLIC_API_URL",
    description: "Backend API base URL",
    required: true,
    validate: (v) => v.startsWith("http://") || v.startsWith("https://"),
  },
  {
    variable: "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
    description: "Clerk authentication publishable key",
    required: true,
    validate: (v) => v.startsWith("pk_"),
  },

  // ── Observability (optional) ───────────────────────────────────────
  {
    variable: "NEXT_PUBLIC_SENTRY_DSN",
    description: "Sentry DSN for error tracking",
    required: false,
    validate: (v) => v === "" || v.startsWith("https://"),
  },
];

export interface EnvValidationResult {
  /** Whether all required variables are valid */
  valid: boolean;
  /** List of issues found */
  issues: EnvIssue[];
}

export interface EnvIssue {
  /** The environment variable name */
  variable: string;
  /** Human-readable description */
  description: string;
  /** Severity: "error" (app won't work) or "warning" (degraded) */
  severity: "error" | "warning";
  /** Specific error message */
  message: string;
}

/**
 * Validate all required environment variables.
 * Call this once during app initialisation.
 */
export function validateEnvironment(): EnvValidationResult {
  const issues: EnvIssue[] = [];

  for (const req of REQUIREMENTS) {
    const value = process.env[req.variable] ?? "";

    if (!value) {
      if (req.required) {
        issues.push({
          variable: req.variable,
          description: req.description,
          severity: "error",
          message: `Missing required environment variable: ${req.variable} (${req.description}). ` +
            `Set it in .env.local or your hosting dashboard.`,
        });
      }
      continue;
    }

    if (req.validate && !req.validate(value)) {
      issues.push({
        variable: req.variable,
        description: req.description,
        severity: req.required ? "error" : "warning",
        message: `Invalid value for ${req.variable}: "${value}". Expected format: ${req.description}.`,
      });
    }
  }

  return {
    valid: issues.filter((i) => i.severity === "error").length === 0,
    issues,
  };
}

/**
 * Format validation results as a human-readable string.
 * Useful for console output during development.
 */
export function formatValidationResult(result: EnvValidationResult): string {
  if (result.valid && result.issues.length === 0) {
    return "✅ All environment variables are valid.";
  }

  const lines: string[] = [];
  for (const issue of result.issues) {
    const icon = issue.severity === "error" ? "❌" : "⚠️";
    lines.push(`${icon} [${issue.severity.toUpperCase()}] ${issue.message}`);
  }

  if (result.valid) {
    lines.unshift("⚠️ Environment has warnings (non-critical):");
  } else {
    lines.unshift("❌ Environment validation failed:");
  }

  return lines.join("\n");
}
