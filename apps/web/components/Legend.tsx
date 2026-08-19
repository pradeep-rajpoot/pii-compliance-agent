import type { Detection } from "@/lib/types";
import { getPiiColorEntry } from "@/lib/piiColors";
import styles from "./Legend.module.css";

interface LegendProps {
  detections: Detection[];
}

/** One swatch+label per distinct pii_type actually present in `detections`. */
export default function Legend({ detections }: LegendProps) {
  const distinctTypes = Array.from(new Set(detections.map((detection) => detection.pii_type)));

  if (distinctTypes.length === 0) {
    return null;
  }

  return (
    <ul className={styles.legend} aria-label="PII type legend">
      {distinctTypes.map((piiType) => {
        const { label, color } = getPiiColorEntry(piiType);
        return (
          <li key={piiType} className={styles.item}>
            <span className={styles.swatch} style={{ backgroundColor: color }} aria-hidden="true" />
            <span>{label}</span>
          </li>
        );
      })}
    </ul>
  );
}
