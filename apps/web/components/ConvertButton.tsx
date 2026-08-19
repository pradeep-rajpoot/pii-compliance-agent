import type { JobStatus } from "@/lib/types";
import styles from "./ConvertButton.module.css";

interface ConvertButtonProps {
  status: JobStatus | "idle";
  onClick: () => void;
}

/**
 * Enabled only once `status === "detected"` -- deliberately NOT gated on
 * detections.length > 0, so a zero-PII document can still produce a
 * pass-through copy. Visible-but-disabled once a job exists (any status
 * other than "idle") so the user sees the workflow shape early.
 */
export default function ConvertButton({ status, onClick }: ConvertButtonProps) {
  if (status === "idle") {
    return null;
  }

  const isCorrecting = status === "correcting";
  const isEnabled = status === "detected";

  return (
    <button type="button" className={styles.button} onClick={onClick} disabled={!isEnabled}>
      {isCorrecting && <span className={styles.spinner} aria-hidden="true" />}
      {isCorrecting ? "Converting…" : "Convert to PII Safe"}
    </button>
  );
}
