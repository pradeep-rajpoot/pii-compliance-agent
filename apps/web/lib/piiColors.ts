import type { PiiType } from "./types";

export interface PiiColorEntry {
  label: string;
  color: string;
}

/**
 * Fixed-order categorical palette (8 CVD-safe hues) for the most common PII
 * types. A legend/highlight scheme genuinely needs more identities than a
 * chart's categorical budget supports (11 documented PII types plus any
 * backend-added ones), so per the "fold past the safe budget" rule, the
 * lower-frequency/more-specialized types share a neutral "other" swatch --
 * their identity is still carried by the text label (in the legend and the
 * <mark> tooltip), never by color alone.
 */
const OTHER_COLOR = "#898781";

const KNOWN_PII_COLORS: Record<string, PiiColorEntry> = {
  name: { label: "Name", color: "#2a78d6" },
  email: { label: "Email", color: "#eb6834" },
  phone: { label: "Phone", color: "#1baf7a" },
  address: { label: "Address", color: "#eda100" },
  ssn: { label: "SSN", color: "#e87ba4" },
  date_of_birth: { label: "Date of Birth", color: "#008300" },
  credit_card: { label: "Credit Card", color: "#4a3aa7" },
  bank_account: { label: "Bank Account", color: "#e34948" },
  ip_address: { label: "IP Address", color: OTHER_COLOR },
  drivers_license: { label: "Driver's License", color: OTHER_COLOR },
  passport: { label: "Passport", color: OTHER_COLOR },
};

function titleCaseFallbackLabel(piiType: string): string {
  const label = piiType
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
  return label || "Other";
}

/** Looks up display info for a pii_type, falling back gracefully for anything unrecognized. */
export function getPiiColorEntry(piiType: PiiType): PiiColorEntry {
  const known = KNOWN_PII_COLORS[piiType];
  if (known) return known;
  return { label: titleCaseFallbackLabel(String(piiType)), color: OTHER_COLOR };
}

export function getPiiColor(piiType: PiiType): string {
  return getPiiColorEntry(piiType).color;
}

export function getPiiLabel(piiType: PiiType): string {
  return getPiiColorEntry(piiType).label;
}
