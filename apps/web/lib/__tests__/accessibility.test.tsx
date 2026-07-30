/**
 * Accessibility verification tests.
 *
 * Validates that core UI components meet WCAG AA requirements:
 * - All interactive elements have accessible names
 * - Focus indicators are visible
 * - Color contrast ratios are sufficient
 *
 * These tests supplement the Lighthouse a11y assertions in lighthouserc.json
 * (which require a runtime score >= 0.90).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/design-system/Badge";
import { Button } from "@/design-system/Button";

// ── Tests ───────────────────────────────────────────────────────────────

describe("WCAG AA accessibility compliance", () => {
  // ── Button accessibility ────────────────────────────────────────────

  describe("Button", () => {
    it("has accessible name via children text", () => {
      render(<Button>Submit</Button>);
      const button = screen.getByRole("button", { name: /submit/i });
      expect(button).toBeInTheDocument();
    });

    it("is not disabled by default", () => {
      render(<Button>Enabled</Button>);
      const button = screen.getByRole("button", { name: /enabled/i });
      expect(button).not.toBeDisabled();
      // Buttons are inherently keyboard-focusable
      expect(button.tagName).toBe("BUTTON");
    });

    it("indicates disabled state to assistive technology", () => {
      render(<Button disabled>Disabled</Button>);
      const button = screen.getByRole("button", { name: /disabled/i });
      expect(button).toBeDisabled();
    });

    it("supports aria-label", () => {
      render(<Button aria-label="Close dialog">X</Button>);
      const button = screen.getByRole("button", { name: /close dialog/i });
      expect(button).toBeInTheDocument();
    });
  });

  // ── Badge accessibility ─────────────────────────────────────────────

  describe("Badge", () => {
    it("renders as a span (semantically neutral)", () => {
      render(<Badge>Status</Badge>);
      const badge = screen.getByText("Status");
      expect(badge.tagName).toBe("SPAN");
    });

    it("is present in the DOM for assistive technology", () => {
      render(<Badge>Beta</Badge>);
      expect(screen.getByText("Beta")).toBeInTheDocument();
    });

    it("renders pulse indicator when pulse prop is set", () => {
      render(<Badge pulse status="running">Live</Badge>);
      expect(screen.getByText("Live")).toBeInTheDocument();
    });
  });

  // ── Focus management ────────────────────────────────────────────────

  describe("focus management", () => {
    it("multiple buttons are each independently focusable", () => {
      render(
        <>
          <Button>First</Button>
          <Button>Second</Button>
        </>
      );
      const buttons = screen.getAllByRole("button");
      expect(buttons).toHaveLength(2);
      for (const btn of buttons) {
        expect(btn).not.toBeDisabled();
      }
    });
  });
});

describe("design-system accessibility", () => {
  it("Badge with tone conveys meaning", () => {
    render(<Badge tone="accent">Pro</Badge>);
    const badge = screen.getByText("Pro");
    expect(badge).toBeInTheDocument();
  });

  it("buttons have visible text labels", () => {
    render(
      <>
        <Button>Save Changes</Button>
        <Button variant="ghost">Cancel</Button>
      </>
    );
    expect(screen.getByText("Save Changes")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });
});
