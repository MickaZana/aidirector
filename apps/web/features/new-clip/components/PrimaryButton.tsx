"use client";

import { Button } from "@/features/design-system";

interface PrimaryButtonProps {
  children: React.ReactNode;
  disabled?: boolean;
  loading?: boolean;
  onClick?: () => void;
  type?: "button" | "submit";
}

/**
 * Large, centered, emerald-green primary CTA button.
 * Disabled until video is uploaded.
 * Uses design-system Button with xl size.
 */
export function PrimaryButton({
  children,
  disabled = false,
  loading = false,
  onClick,
  type = "button",
}: PrimaryButtonProps) {
  return (
    <div className="flex justify-center">
      <Button
        type={type}
        size="xl"
        variant="primary"
        disabled={disabled}
        loading={loading}
        onClick={onClick}
      >
        {children}
      </Button>
    </div>
  );
}
