import { describe, it, expect, beforeEach } from "vitest";
import { useToastStore } from "@/stores/toast-store";

describe("toast-store", () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
  });

  it("starts with empty toasts", () => {
    expect(useToastStore.getState().toasts).toEqual([]);
  });

  it("adds a toast", () => {
    const id = useToastStore.getState().add({
      variant: "info",
      title: "Test toast",
    });

    const state = useToastStore.getState();
    expect(state.toasts).toHaveLength(1);
    expect(state.toasts[0].title).toBe("Test toast");
    expect(state.toasts[0].variant).toBe("info");
    expect(state.toasts[0].id).toBe(id);
  });

  it("removes a toast by id", () => {
    const id = useToastStore.getState().add({
      variant: "info",
      title: "Test",
    });
    useToastStore.getState().remove(id);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("clears all toasts", () => {
    useToastStore.getState().add({ variant: "info", title: "A" });
    useToastStore.getState().add({ variant: "info", title: "B" });
    useToastStore.getState().clear();
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });
});
