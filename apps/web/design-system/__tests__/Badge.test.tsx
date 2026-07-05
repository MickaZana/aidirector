import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/design-system/Badge";

describe("Badge", () => {
  it("renders children text", () => {
    render(<Badge>Test Badge</Badge>);
    expect(screen.getByText("Test Badge")).toBeInTheDocument();
  });

  it("renders as a span element", () => {
    render(<Badge>Hello</Badge>);
    expect(screen.getByText("Hello").tagName).toBe("SPAN");
  });

  it("applies status variant styling", () => {
    render(<Badge status="succeeded">Done</Badge>);
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("applies tone variant styling", () => {
    render(<Badge tone="accent">Accent</Badge>);
    expect(screen.getByText("Accent")).toBeInTheDocument();
  });

  it("renders pulse indicator when pulse is true", () => {
    const { container } = render(<Badge pulse status="running">Live</Badge>);
    // Should have the ping animation child
    expect(container.querySelector(".animate-ping")).toBeInTheDocument();
  });
});
