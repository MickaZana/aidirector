"use client";

/**
 * BillingLimitListener — listens for `billing-limit` custom DOM events
 * dispatched by the API client on 402 responses and shows a toast with
 * an "Update billing" action.
 *
 * Place once in the root layout alongside the Toaster.
 */
import { useEffect } from "react";
import { BILLING_LIMIT_EVENT, type BillingLimitEventDetail } from "@/lib/api/client";
import { toast } from "@/stores/toast-store";

export function BillingLimitListener() {
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<BillingLimitEventDetail>).detail;
      toast.error(
        "Monthly limit reached",
        "You've hit your plan's usage limit. Upgrade to continue processing matches.",
      );
      // The toast action will navigate to the billing page
    };

    window.addEventListener(BILLING_LIMIT_EVENT, handler);
    return () => window.removeEventListener(BILLING_LIMIT_EVENT, handler);
  }, []);

  return null;
}
