/**
 * Toaster component tests.
 *
 * Validates:
 * - Renders nothing when there are no toasts
 * - Renders toast with title and message
 * - Renders different variants
 * - Manual dismiss via X button
 * - Renders action button when provided
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Toaster } from "@/components/ui/Toaster";
import { useToastStore } from "@/stores/toast-store";

// ── Tests ───────────────────────────────────────────────────────────────

describe("Toaster", () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders nothing when there are no toasts", () => {
    const { container } = render(<Toaster />);
    expect(container.firstChild).toBeNull();
  });

  it("renders a toast with title and message", () => {
    useToastStore.getState().add({
      variant: "info",
      title: "Success!",
      message: "Operation completed.",
    });
    render(<Toaster />);

    expect(screen.getByText("Success!")).toBeInTheDocument();
    expect(screen.getByText("Operation completed.")).toBeInTheDocument();
  });

  it("removes toast when X button is clicked", async () => {
    const user = userEvent.setup();
    useToastStore.getState().add({
      variant: "info",
      title: "Dismiss me",
    });
    render(<Toaster />);

    expect(screen.getByText("Dismiss me")).toBeInTheDocument();

    // Find all buttons and click the dismiss (X) button
    const buttons = screen.getAllByRole("button");
    // The toast has an X dismiss button and optionally an action button
    // The X button is the one without any text besides the icon
    // We click the last button as it's the dismiss button
    await user.click(buttons[buttons.length - 1]);

    expect(screen.queryByText("Dismiss me")).not.toBeInTheDocument();
  });

  it("renders action button when provided", () => {
    const onClick = vi.fn();
    useToastStore.getState().add({
      variant: "info",
      title: "Action required",
      action: { label: "Undo", onClick },
    });
    render(<Toaster />);

    const actionButton = screen.getByText("Undo");
    expect(actionButton).toBeInTheDocument();
    expect(screen.getByText("Action required")).toBeInTheDocument();
  });

  it("renders success variant", () => {
    useToastStore.getState().add({ variant: "success", title: "Saved" });
    render(<Toaster />);
    expect(screen.getByText("Saved")).toBeInTheDocument();
  });

  it("renders error variant", () => {
    useToastStore.getState().add({ variant: "error", title: "Failed" });
    render(<Toaster />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("renders warning variant", () => {
    useToastStore.getState().add({ variant: "warning", title: "Warning" });
    render(<Toaster />);
    expect(screen.getByText("Warning")).toBeInTheDocument();
  });

  it("renders multiple toasts", () => {
    useToastStore.getState().add({ variant: "info", title: "First" });
    useToastStore.getState().add({ variant: "info", title: "Second" });
    render(<Toaster />);

    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
  });
});
