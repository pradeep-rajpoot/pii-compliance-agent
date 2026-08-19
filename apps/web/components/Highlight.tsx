import type { Detection } from "@/lib/types";
import { getPiiColor, getPiiLabel } from "@/lib/piiColors";

interface HighlightProps {
  text: string;
  detection: Detection;
}

/** Colored inline highlight for a single PII span, with a native tooltip (type + confidence). */
export default function Highlight({ text, detection }: HighlightProps) {
  const color = getPiiColor(detection.pii_type);
  const label = getPiiLabel(detection.pii_type);
  const confidencePct = Math.round(detection.confidence * 100);

  return (
    <mark
      data-pii-type={detection.pii_type}
      style={{ backgroundColor: color }}
      title={`${label} • ${confidencePct}%`}
    >
      {text}
    </mark>
  );
}
