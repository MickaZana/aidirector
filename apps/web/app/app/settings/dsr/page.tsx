"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Shield,
  Trash2,
  XCircle,
} from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
import { TopBar } from "@/components/layout/TopBar";
import { Badge } from "@/design-system/Badge";
import { Button } from "@/design-system/Button";
import { useApi } from "@/lib/api/runtime";
import { toast } from "@/stores/toast-store";

// ── Types ───────────────────────────────────────────────────────────────────

interface DeletionStatus {
  tenant_id: string;
  deletion_requested: boolean;
  deletion_requested_at: string | null;
  deletion_scheduled_for: string | null;
  deletion_cancelled: boolean;
  grace_days: number;
  days_remaining: number | null;
}

interface ExportData {
  generated_at: string;
  schema_version: string;
  account: Record<string, unknown>;
  uploads: unknown[];
  jobs: unknown[];
  [key: string]: unknown;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function daysLabel(days: number | null): string {
  if (days === null || days === undefined) return "—";
  if (days === 0) return "Today";
  if (days === 1) return "1 day";
  return `${days} days`;
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function DsrSettingsPage() {
  const { endpoints, mode } = useApi();

  // Deletion state
  const [deletionStatus, setDeletionStatus] = useState<DeletionStatus | null>(null);
  const [deletionLoading, setDeletionLoading] = useState(true);
  const [requestingDeletion, setRequestingDeletion] = useState(false);
  const [cancellingDeletion, setCancellingDeletion] = useState(false);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);

  // Export state
  const [exporting, setExporting] = useState(false);
  const [exportData, setExportData] = useState<ExportData | null>(null);
  const [showExportJson, setShowExportJson] = useState(false);

  // ── Fetch deletion status ──────────────────────────────────────────────

  const fetchStatus = useCallback(async () => {
    if (mode === "fixtures" || !endpoints) {
      setDeletionStatus({
        tenant_id: "demo",
        deletion_requested: true,
        deletion_requested_at: new Date(Date.now() - 7 * 86400000).toISOString(),
        deletion_scheduled_for: new Date(Date.now() + 23 * 86400000).toISOString(),
        deletion_cancelled: false,
        grace_days: 30,
        days_remaining: 23,
      });
      setDeletionLoading(false);
      return;
    }

    try {
      const status = await endpoints.getDsrDeletionStatus();
      setDeletionStatus(status);
    } catch {
      setDeletionStatus(null);
    } finally {
      setDeletionLoading(false);
    }
  }, [endpoints, mode]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // ── Request deletion ───────────────────────────────────────────────────

  const handleRequestDeletion = async () => {
    setConfirmDialogOpen(false);
    if (!endpoints) return;

    setRequestingDeletion(true);
    try {
      const result = await endpoints.requestDsrDeletion();
      toast.success(
        "Deletion scheduled",
        `Your account will be permanently deleted on ${formatDate(result.deletion_scheduled_for)}.`,
      );
      await fetchStatus();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not request deletion";
      toast.error("Failed to request deletion", msg);
    } finally {
      setRequestingDeletion(false);
    }
  };

  // ── Cancel deletion ────────────────────────────────────────────────────

  const handleCancelDeletion = async () => {
    if (!endpoints) return;

    setCancellingDeletion(true);
    try {
      await endpoints.cancelDsrDeletion();
      toast.success("Deletion cancelled", "Your data will be preserved.");
      await fetchStatus();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not cancel deletion";
      toast.error("Failed to cancel deletion", msg);
    } finally {
      setCancellingDeletion(false);
    }
  };

  // ── Export data ─────────────────────────────────────────────────────────

  const handleExportData = async () => {
    if (!endpoints) {
      // Fixture mode — show mock data
      setExportData({
        generated_at: new Date().toISOString(),
        schema_version: "1",
        account: { tenant: { name: "Demo Org", plan: "starter" }, users: [] },
        uploads: [],
        jobs: [],
      });
      setShowExportJson(true);
      return;
    }

    setExporting(true);
    try {
      const data = await endpoints.exportDsrData();
      setExportData(data);
      setShowExportJson(true);
      toast.success("Data exported", "Your data is ready to review.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not export data";
      toast.error("Failed to export data", msg);
    } finally {
      setExporting(false);
    }
  };

  // ── Render helpers ──────────────────────────────────────────────────────

  const isPending =
    deletionStatus?.deletion_requested && !deletionStatus?.deletion_cancelled;

  /** Renders the action button based on current deletion state. */
  function renderActionButton() {
    if (deletionLoading) {
      return (
        <div className="text-xs animate-pulse" style={{ color: "var(--color-text-tertiary)" }}>
          Checking…
        </div>
      );
    }
    if (isPending) {
      return (
        <Button variant="secondary" size="sm" onClick={handleCancelDeletion} disabled={cancellingDeletion}>
          {cancellingDeletion ? "Cancelling…" : "Cancel deletion"}
        </Button>
      );
    }
    if (deletionStatus?.deletion_cancelled) {
      return null;
    }
    return (
      <Dialog.Root open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <Dialog.Trigger asChild>
          <Button variant="danger" size="sm" disabled={requestingDeletion}>
            {requestingDeletion ? "Requesting…" : "Request deletion"}
          </Button>
        </Dialog.Trigger>

        <Dialog.Portal>
          <Dialog.Overlay
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in"
            style={{ animation: "fade-in 150ms ease-out" }}
          />
          <Dialog.Content
            className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-full max-w-md rounded-xl p-6 shadow-[var(--shadow-elevated)]"
            style={{
              background: "var(--color-surface-2)",
              border: "1px solid var(--color-border-strong)",
            }}
          >
            <div className="flex items-center gap-3 mb-4">
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                style={{ background: "rgba(255, 77, 141, 0.2)" }}
              >
                <AlertTriangle
                  className="h-5 w-5"
                  style={{ color: "var(--color-accent-magenta)" }}
                  strokeWidth={2}
                />
              </div>
              <div>
                <Dialog.Title className="text-sm font-semibold" style={{ color: "var(--color-text-primary)" }}>
                  Delete your account?
                </Dialog.Title>
                <Dialog.Description className="text-xs mt-1" style={{ color: "var(--color-text-secondary)" }}>
                  This will permanently delete all your data. You have 30 days to cancel.
                </Dialog.Description>
              </div>
            </div>

            <div
              className="rounded-lg p-3 mb-4 text-xs space-y-1"
              style={{
                background: "rgba(255, 77, 141, 0.08)",
                border: "1px solid rgba(255, 77, 141, 0.2)",
              }}
            >
              <div className="flex items-center gap-2" style={{ color: "var(--color-accent-magenta)" }}>
                <Shield className="h-3.5 w-3.5" strokeWidth={2} />
                <span className="font-medium">What happens next</span>
              </div>
              <ul className="list-disc pl-5 mt-1 space-y-0.5" style={{ color: "var(--color-text-secondary)" }}>
                <li>A 30-day grace period starts immediately</li>
                <li>You can use the service normally during this time</li>
                <li>After 30 days, all data is permanently deleted</li>
                <li>This action cannot be undone after the grace period</li>
              </ul>
            </div>

            <div className="flex items-center justify-end gap-2">
              <Dialog.Close asChild>
                <Button variant="secondary" size="sm">
                  Keep my account
                </Button>
              </Dialog.Close>
              <Button variant="danger" size="sm" onClick={handleRequestDeletion}>
                Confirm deletion
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    );
  }

  return (
    <>
      <TopBar
        title="Data & Privacy"
        subtitle="Manage your data, request account deletion, or export your information"
      />

      <div className="px-6 lg:px-8 py-8 max-w-3xl space-y-8">
        {/* ── Data Export Card ─────────────────────────────────────────── */}
        <div
          className="rounded-xl p-6"
          style={{
            background: "var(--color-surface-1)",
            border: "1px solid var(--color-border-soft)",
          }}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div
                className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-lg"
                style={{
                  background: "var(--color-accent-blue)",
                  opacity: 0.15,
                  border: "1px solid rgba(61, 169, 252, 0.3)",
                }}
              >
                <Download
                  className="h-5 w-5"
                  style={{ color: "var(--color-accent-blue)" }}
                  strokeWidth={2}
                />
              </div>
              <div>
                <div className="text-sm font-semibold" style={{ color: "var(--color-text-primary)" }}>
                  Export your data
                </div>
                <p className="text-xs mt-1 max-w-md" style={{ color: "var(--color-text-secondary)" }}>
                  Download all your personal data in a structured format (GDPR Article 20).
                  Includes account details, uploads, jobs, clips, renders, and usage history.
                </p>
              </div>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleExportData}
              disabled={exporting}
            >
              {exporting ? "Exporting…" : "Export data"}
            </Button>
          </div>

          {/* Export result JSON */}
          {showExportJson && exportData && (
            <div
              className="mt-4 rounded-lg p-4 overflow-auto max-h-80"
              style={{
                background: "var(--color-surface-0)",
                border: "1px solid var(--color-border-soft)",
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2
                    className="h-3.5 w-3.5"
                    style={{ color: "var(--color-accent-green)" }}
                    strokeWidth={2}
                  />
                  <span
                    className="text-xs font-medium"
                    style={{ color: "var(--color-accent-green)" }}
                  >
                    Export generated&nbsp;
                    {formatDate(exportData.generated_at)}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(JSON.stringify(exportData, null, 2));
                    toast.success("Copied to clipboard");
                  }}
                >
                  Copy JSON
                </Button>
              </div>
              <pre
                className="text-xs leading-relaxed whitespace-pre-wrap"
                style={{ color: "var(--color-text-secondary)" }}
              >
                {JSON.stringify(
                  {
                    schema_version: exportData.schema_version,
                    generated_at: exportData.generated_at,
                    account: exportData.account,
                    uploads_count: exportData.uploads?.length ?? 0,
                    jobs_count: exportData.jobs?.length ?? 0,
                  },
                  null,
                  2,
                )}
              </pre>
              <button
                onClick={() => setShowExportJson(false)}
                className="mt-2 text-xs font-medium transition-colors"
                style={{ color: "var(--color-text-tertiary)" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--color-text-secondary)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--color-text-tertiary)")}
              >
                Hide preview
              </button>
            </div>
          )}
        </div>

        {/* ── Account Deletion Card ────────────────────────────────────── */}
        <div
          className="rounded-xl p-6"
          style={{
            background: "var(--color-surface-1)",
            border: "1px solid var(--color-border-soft)",
          }}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div
                className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-lg"
                style={{
                  background: "var(--color-accent-magenta)",
                  opacity: 0.15,
                  border: "1px solid rgba(255, 77, 141, 0.3)",
                }}
              >
                <Trash2
                  className="h-5 w-5"
                  style={{ color: "var(--color-accent-magenta)" }}
                  strokeWidth={2}
                />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className="text-sm font-semibold"
                    style={{ color: "var(--color-text-primary)" }}
                  >
                    Delete account
                  </span>
                  {deletionLoading ? null : isPending ? (
                    <Badge tone="warning">Pending deletion</Badge>
                  ) : deletionStatus?.deletion_cancelled ? (
                    <Badge tone="neutral">Deletion cancelled</Badge>
                  ) : null}
                </div>
                <p className="text-xs mt-1 max-w-md" style={{ color: "var(--color-text-secondary)" }}>
                  Permanently delete your account and all associated data. A 30-day grace period
                  applies during which you can cancel the request.
                </p>
              </div>
            </div>

            {/* Action button */}
            {renderActionButton()}
          </div>

          {/* Deletion status details */}
          {!deletionLoading && isPending && (
            <div
              className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-4 rounded-lg p-4"
              style={{
                background: "rgba(247, 201, 72, 0.06)",
                border: "1px solid rgba(247, 201, 72, 0.2)",
              }}
            >
              <div>
                <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--color-text-tertiary)" }}>
                  Requested
                </div>
                <div className="text-sm font-medium" style={{ color: "var(--color-text-primary)" }}>
                  {formatDate(deletionStatus.deletion_requested_at)}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--color-text-tertiary)" }}>
                  Scheduled deletion
                </div>
                <div className="text-sm font-medium" style={{ color: "var(--color-accent-magenta)" }}>
                  {formatDate(deletionStatus.deletion_scheduled_for)}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--color-text-tertiary)" }}>
                  Time remaining
                </div>
                <div
                  className="text-sm font-semibold tabular-nums"
                  style={{
                    color:
                      (deletionStatus.days_remaining ?? 30) <= 3
                        ? "var(--color-accent-magenta)"
                        : "var(--color-accent-gold)",
                  }}
                >
                  {daysLabel(deletionStatus.days_remaining)}
                </div>
              </div>
            </div>
          )}

          {/* Cancelled notice */}
          {!deletionLoading && deletionStatus?.deletion_cancelled && (
            <div
              className="mt-5 flex items-center gap-2 rounded-lg p-4"
              style={{
                background: "rgba(61, 169, 252, 0.06)",
                border: "1px solid rgba(61, 169, 252, 0.2)",
              }}
            >
              <XCircle
                className="h-4 w-4 shrink-0"
                style={{ color: "var(--color-accent-blue)" }}
                strokeWidth={2}
              />
              <div className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                Your deletion request was cancelled. Your data is safe. You can request
                deletion again at any time.
              </div>
            </div>
          )}
        </div>

        {/* ── GDPR Info Card ───────────────────────────────────────────── */}
        <div
          className="rounded-xl p-4 flex items-start gap-3"
          style={{
            background: "var(--color-surface-1)",
            border: "1px solid var(--color-border-soft)",
          }}
        >
          <Shield
            className="h-4 w-4 shrink-0 mt-0.5"
            style={{ color: "var(--color-text-tertiary)" }}
            strokeWidth={2}
          />
          <div className="text-xs leading-relaxed" style={{ color: "var(--color-text-tertiary)" }}>
            We take your data privacy seriously. All data is encrypted at rest and in transit.
            Your data is processed in accordance with GDPR and CCPA regulations. For additional
            requests, contact{" "}
            <span
              className="font-medium"
              style={{ color: "var(--color-text-secondary)" }}
            >
              privacy@omegaclips.io
            </span>
            .
          </div>
        </div>
      </div>
    </>
  );
}
