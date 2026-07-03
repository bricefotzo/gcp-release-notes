import styles from "./Badge.module.css";

const LABELS: Record<string, string> = {
  FEATURE:        "Feature",
  FIX:            "Fix",
  BREAKING_CHANGE:"Breaking",
  DEPRECATION:    "Deprecated",
  ISSUE:          "Issue",
  ANNOUNCEMENT:   "Announcement",
};

const VARIANTS: Record<string, string> = {
  FEATURE:        "feature",
  FIX:            "fix",
  BREAKING_CHANGE:"breaking",
  DEPRECATION:    "deprecation",
  ISSUE:          "issue",
  ANNOUNCEMENT:   "announcement",
};

export default function Badge({ type }: { type: string }) {
  const key = type?.toUpperCase();
  return (
    <span className={`${styles.badge} ${styles[VARIANTS[key] ?? "default"]}`}>
      {LABELS[key] ?? type}
    </span>
  );
}
