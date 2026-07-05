import { describe, it, expect } from "vitest";
import {
  formatPercent, formatScore, shortenId, shortenHash,
  formatCents, formatRelativeTime, formatBytes, formatSeconds,
} from "@/lib/format";

describe("formatPercent", () => {
  it("formats 0.5 as 50%", () => expect(formatPercent(0.5)).toBe("50%"));
  it("formats 0.1234 as 12%", () => expect(formatPercent(0.1234)).toBe("12%"));
  it("formats 1 as 100%", () => expect(formatPercent(1)).toBe("100%"));
  it("formats 0 as 0%", () => expect(formatPercent(0)).toBe("0%"));
  it("handles null", () => expect(formatPercent(null)).toBe("—"));
});

describe("formatScore", () => {
  it("formats with 3 decimal places", () => expect(formatScore(0.5)).toBe("0.500"));
  it("formats 0 as 0.000", () => expect(formatScore(0)).toBe("0.000"));
  it("formats 1 as 1.000", () => expect(formatScore(1)).toBe("1.000"));
  it("handles null", () => expect(formatScore(null)).toBe("—"));
});

describe("shortenId", () => {
  it("shortens UUID to first segment", () => {
    expect(shortenId("123e4567-e89b-12d3-a456-426614174000")).toBe("123e4567");
  });
  it("handles short strings", () => expect(shortenId("abc")).toBe("abc"));
  it("handles null", () => expect(shortenId(null)).toBe("—"));
});

describe("shortenHash", () => {
  it("returns full string if shorter than 2*chars+1", () => {
    expect(shortenHash("abcdef1234567890")).toBe("abcdef1234567890");
  });
  it("truncates long hashes with ellipsis", () => {
    expect(shortenHash("abcdef1234567890abcdef1234567890abcdef12")).toBe("abcdef1234…ef12");
  });
  it("handles null", () => expect(shortenHash(null)).toBe("—"));
});

describe("formatCents", () => {
  it("formats 0 cents as $0.00", () => expect(formatCents(0)).toBe("$0.00"));
  it("formats 100 cents as $1.00", () => expect(formatCents(100)).toBe("$1.00"));
  it("formats 1234 cents as $12.34", () => expect(formatCents(1234)).toBe("$12.34"));
  it("formats negative cents as $-", () => expect(formatCents(-500)).toBe("$-5.00"));
  it("handles null", () => expect(formatCents(null)).toBe("—"));
});

describe("formatRelativeTime", () => {
  it('returns seconds ago', () => {
    const now = new Date().toISOString();
    const result = formatRelativeTime(now);
    expect(result).toMatch(/^\d+s ago$/);
  });
  it("handles null", () => expect(formatRelativeTime(null)).toBe("—"));
});

describe("formatBytes", () => {
  it("formats bytes", () => expect(formatBytes(1024)).toBe("1.0 KB"));
  it("formats megabytes", () => expect(formatBytes(1048576)).toBe("1.0 MB"));
  it("handles null", () => expect(formatBytes(null)).toBe("—"));
});

describe("formatSeconds", () => {
  it("formats seconds", () => expect(formatSeconds(90)).toBe("1m 30s"));
  it("formats sub-minute", () => expect(formatSeconds(45.5)).toBe("45.5s"));
  it("handles null", () => expect(formatSeconds(null)).toBe("—"));
});
