import { downloadUrl } from "@/lib/apiClient";
import type { JobStatus } from "@/lib/types";
import styles from "./DownloadButton.module.css";

interface DownloadButtonProps {
  jobId: string;
  status: JobStatus | "idle";
}

/**
 * Renders nothing unless status === "corrected". A plain anchor pointing at
 * the download endpoint -- lets the browser stream the response and honor
 * the server's Content-Disposition filename, no fetch+blob.
 */
export default function DownloadButton({ jobId, status }: DownloadButtonProps) {
  if (status !== "corrected") {
    return null;
  }

  return (
    <a className={styles.button} href={downloadUrl(jobId)} download>
      Download PII-safe file
    </a>
  );
}
