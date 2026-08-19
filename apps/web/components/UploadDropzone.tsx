"use client";

import { useCallback, useId, useRef, useState, type ChangeEvent, type DragEvent, type KeyboardEvent } from "react";
import { ACCEPTED_EXTENSIONS, ACCEPTED_EXTENSIONS_ACCEPT_ATTR, MAX_UPLOAD_BYTES } from "@/lib/constants";
import styles from "./UploadDropzone.module.css";

export interface UploadValidationError {
  code: "UNSUPPORTED_FILE_TYPE" | "FILE_TOO_LARGE";
  message: string;
}

interface UploadDropzoneProps {
  onFileAccepted: (file: File) => void;
  onValidationError: (error: UploadValidationError) => void;
  disabled?: boolean;
}

function getExtension(filename: string): string {
  const idx = filename.lastIndexOf(".");
  return idx === -1 ? "" : filename.slice(idx).toLowerCase();
}

function formatBytes(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

/** Drag-and-drop upload zone with client-side extension/size validation. */
export default function UploadDropzone({ onFileAccepted, onValidationError, disabled = false }: UploadDropzoneProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const labelId = useId();

  const validateAndAccept = useCallback(
    (file: File) => {
      // Case-insensitive filename suffix check, not MIME sniffing -- the
      // backend applies the same rule, so rejections read consistently
      // regardless of where they happen.
      const ext = getExtension(file.name);
      if (!(ACCEPTED_EXTENSIONS as readonly string[]).includes(ext)) {
        onValidationError({
          code: "UNSUPPORTED_FILE_TYPE",
          message: `"${ext || file.name}" isn't a supported file type. Accepted types: ${ACCEPTED_EXTENSIONS.join(", ")}.`,
        });
        return;
      }

      if (file.size > MAX_UPLOAD_BYTES) {
        onValidationError({
          code: "FILE_TOO_LARGE",
          message: `File is ${formatBytes(file.size)}, which exceeds the ${formatBytes(MAX_UPLOAD_BYTES)} limit.`,
        });
        return;
      }

      onFileAccepted(file);
    },
    [onFileAccepted, onValidationError],
  );

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragActive(false);
      if (disabled) return;
      const file = event.dataTransfer.files?.[0];
      if (file) validateAndAccept(file);
    },
    [disabled, validateAndAccept],
  );

  const handleInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) validateAndAccept(file);
      // Reset so selecting the same file again still fires onChange.
      event.target.value = "";
    },
    [validateAndAccept],
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (disabled) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        inputRef.current?.click();
      }
    },
    [disabled],
  );

  return (
    <div
      className={[styles.dropzone, isDragActive ? styles.active : "", disabled ? styles.disabled : ""]
        .filter(Boolean)
        .join(" ")}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setIsDragActive(true);
      }}
      onDragLeave={() => setIsDragActive(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-labelledby={labelId}
    >
      <p id={labelId} className={styles.label}>
        Drag and drop a file here, or click to browse
      </p>
      <p className={styles.hint}>
        Accepted: {ACCEPTED_EXTENSIONS.join(", ")} (max {formatBytes(MAX_UPLOAD_BYTES)})
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS_ACCEPT_ATTR}
        onChange={handleInputChange}
        disabled={disabled}
        className={styles.hiddenInput}
        tabIndex={-1}
        aria-hidden="true"
      />
    </div>
  );
}
