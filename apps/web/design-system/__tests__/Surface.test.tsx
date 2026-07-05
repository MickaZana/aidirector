import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Surface } from "@/design-system/Surface";

describe("Surface", () => {
  it("renders children", () => {
    render(<Surface>Content</Surface>);
    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  it("renders as a div by default", () => {
    render(<Surface>Div</Surface>);
    expect(screen.getByText("Div").tagName).toBe("DIV");
  });

  it("applies variant classes", () => {
    const { container } = render(<Surface variant="card">Card</Surface>);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("applies dense padding when dense prop is set", () => {
    const { container } = render(<Surface dense>Dense</Surface>);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("applies interactive styles when interactive prop is set", () => {
    const { container } = render(<Surface interactive>Interactive</Surface>);
    expect(container.firstChild).toBeInTheDocument();
  });

  it("accepts and applies className", () => {
    const { container } = render(<Surface className="custom-class">Custom</Surface>);
    expect(container.firstChild).toHaveClass("custom-class");
  });
});
