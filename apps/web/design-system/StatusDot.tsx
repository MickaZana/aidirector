import * as React from "react";
import { cn } from "@/lib/cn";
import { STATUS_COLORS, type StatusKey } from "./tokens";

interface StatusDotProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: StatusKey;
  size?: "sm" | "md" | "lg";
  pulse?: boolean;
}

const SIZE: Record<NonNullable<StatusDotProps["size"]>, string> = {
  sm: "h-1.5 w-1.5",
  md: "h-2 w-2",
  lg: "h-2.5 w-2.5",
};

export const StatusDot = React.forwardRef<HTMLSpanElement, StatusDotProps>(
  ({ status, size = "md", pulse, className, style, ...rest }, ref) => (
    <span
      ref={ref}
      className={cn("relative inline-flex shrink-0", SIZE[size], className)}
      style={style}
      {...rest}
    >
      <span
        className={cn("inline-flex h-full w-full rounded-full")}
        style={{ background: STATUS_COLORS[status] }}
      />
      {pulse && (
        <span
          aria-hidden
          className="absolute inset-0 rounded-full opacity-60 animate-ping"
          style={{ background: STATUS_COLORS[status] }}
        />
      )}
    </span>
  ),
);
StatusDot.displayName = "StatusDot";
