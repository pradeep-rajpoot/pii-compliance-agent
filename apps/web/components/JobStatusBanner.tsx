import type { JobErrorInfo, JobStatus } from "@/lib/types";
import styles from "./JobStatusBanner.module.css";

// NOTE: the spec's component list gives this prop type as
// `JobStatus | "idle" | "validation_error" | "upload_error"`, but the page
// state machine (per the spec's own §6 action list) also has an
// "uploading" phase between file selection and getting a job_id back.
// "uploading" is added here so the banner can represent every phase the
// reducer actually produces without a type-unsafe cast at the call site.
export type BannerStatus = JobStatus | "idle" | "validation_error" | "upload_error" | "uploading";

interface JobStatusBannerProps {
  status: BannerStatus;
  error?: JobErrorInfo | null;
}

const ERROR_STATUSES = new Set<BannerStatus>(["failed", "validation_error", "upload_error"]);
const BUSY_STATUSES = new Set<BannerStatus>(["uploading", "queued", "detecting", "correcting"]);

const STATUS_LABELS: Partial<Record<BannerStatus, string>> = {
  idle: "Upload a file to scan it for PII.",
  uploading: "Uploading file…",
  queued: "Queued for detection…",
  detecting: "Scanning document for PII…",
  detected: "Detection complete. Review the highlighted PII below.",
  correcting: "Generating a PII-safe copy…",
  corrected: "PII-safe copy is ready to download.",
};

/** Purely presentational: renders a progress indicator or an error alert. No fetch logic. */
export default function JobStatusBanner({ status, error }: JobStatusBannerProps) {
  if (ERROR_STATUSES.has(status)) {
    return (
      <div className={styles.banner} role="alert" data-variant="error">
        <div>
          <p className={styles.errorTitle}>Something went wrong</p>
          <p className={styles.errorDetail}>
            {error ? (
              <>
                <code>{error.code}</code>: {error.message}
              </>
            ) : (
              "An unknown error occurred."
            )}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.banner} role="status" data-variant={status}>
      {BUSY_STATUSES.has(status) && <span className={styles.spinner} aria-hidden="true" />}
      <p className={styles.label}>{STATUS_LABELS[status] ?? "…"}</p>
    </div>
  );
}
