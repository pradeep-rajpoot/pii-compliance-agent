// Client-side mirror of the backend's upload constraints (mvp-spec.md §11),
// so rejections are instant and consistent regardless of where they happen.

/** Default 10MB upload limit, matching the backend default. */
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

/**
 * Accepted upload extensions. `.doc` (legacy binary Word) is intentionally
 * excluded -- only modern/structured formats the parsers actually support
 * are offered, per product decision.
 */
export const ACCEPTED_EXTENSIONS = [".pdf", ".xls", ".xlsx", ".csv", ".docx", ".json"] as const;

export type AcceptedExtension = (typeof ACCEPTED_EXTENSIONS)[number];

/** Value for the hidden file input's `accept` attribute. */
export const ACCEPTED_EXTENSIONS_ACCEPT_ATTR = ACCEPTED_EXTENSIONS.join(",");

/** Default job-status poll interval. */
export const DEFAULT_POLL_INTERVAL_MS = 1500;

/** Consecutive raw network/fetch failures tolerated before polling gives up. */
export const MAX_CONSECUTIVE_NETWORK_FAILURES = 3;
