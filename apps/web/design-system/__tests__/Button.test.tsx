import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/design-system/Button";

describe("Button", () => {
  it("renders children text", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText("Click me")).toBeInTheDocument();
  });

  it("renders as a button element by default", () => {
    render(<Button>Default</Button>);
    expect(screen.getByText("Default").tagName).toBe("BUTTON");
  });

  it("applies variant classes", () => {
    const { container } = render(<Button variant="ghost">Ghost</Button>);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("applies size classes", () => {
    const { container } = render(<Button size="sm">Small</Button>);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("handles click events", async () => {
    const user = userEvent.setup();
    let clicked = false;
    render(<Button onClick={() => { clicked = true; }}>Click</Button>);
    await user.click(screen.getByText("Click"));
    expect(clicked).toBe(true);
  });

  it("is disabled when disabled prop is set", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByText("Disabled")).toBeDisabled();
  });
});
