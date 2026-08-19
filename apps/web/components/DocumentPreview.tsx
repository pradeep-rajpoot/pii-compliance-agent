import type { Detection, Locator, TextBlock } from "@/lib/types";
import { buildSegments } from "@/lib/highlightSegments";
import Highlight from "./Highlight";
import Legend from "./Legend";
import styles from "./DocumentPreview.module.css";

interface DocumentPreviewProps {
  blocks: TextBlock[];
  detections: Detection[];
}

function titleCase(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

/**
 * Builds a short human-readable badge generically from whatever locator
 * keys are present -- e.g. "Sheet1!B7", "Page 2", "Paragraph 12" -- without
 * hardcoding a fixed shape per file type.
 */
function formatLocator(locator: Locator | undefined): string | null {
  if (!locator) return null;

  const { sheet, cell, page, paragraph, row, column, path, ...rest } = locator;

  if (sheet !== undefined && cell !== undefined) return `${sheet}!${cell}`;
  if (sheet !== undefined) return String(sheet);
  if (typeof page === "number") return `Page ${page}`;
  if (typeof paragraph === "number") return `Paragraph ${paragraph}`;
  if (Array.isArray(path)) {
    // Render list indices with bracket notation (e.g. "contacts[0].phone")
    // to match the JSON parser's own block-id formatting.
    return path.reduce<string>((acc, segment) => {
      if (typeof segment === "number") return `${acc}[${segment}]`;
      return acc ? `${acc}.${segment}` : String(segment);
    }, "");
  }
  if (row !== undefined || column !== undefined) {
    const parts: string[] = [];
    if (row !== undefined) parts.push(`Row ${row}`);
    if (column !== undefined) parts.push(`Col ${column}`);
    return parts.join(", ");
  }

  // Generic fallback for any other/unrecognized locator keys.
  const entries = Object.entries(rest).filter(([, value]) => value !== undefined && value !== null);
  if (entries.length === 0) return null;
  return entries.map(([key, value]) => `${titleCase(key)} ${value}`).join(", ");
}

/** Flat block-list preview: each block's text with detections highlighted inline, plus a legend. */
export default function DocumentPreview({ blocks, detections }: DocumentPreviewProps) {
  return (
    <div className={styles.preview}>
      <Legend detections={detections} />
      {blocks.map((block) => {
        // Detections referencing a block_id with no matching block are
        // silently ignored -- they simply never end up in any block's list.
        const blockDetections = detections.filter((detection) => detection.block_id === block.id);
        const segments = buildSegments(block.text, blockDetections);
        const locatorLabel = formatLocator(block.locator);

        return (
          <div key={block.id} className={styles.block}>
            <div className={styles.blockHeader}>
              <span className={styles.blockId}>{block.id}</span>
              {locatorLabel && <span className={styles.locatorBadge}>{locatorLabel}</span>}
            </div>
            <p className={styles.blockText}>
              {segments.map((segment, index) =>
                segment.detection ? (
                  <Highlight key={`${block.id}-${index}`} text={segment.text} detection={segment.detection} />
                ) : (
                  <span key={`${block.id}-${index}`}>{segment.text}</span>
                ),
              )}
            </p>
          </div>
        );
      })}
    </div>
  );
}
