// Badge colour mapping — mirrors the Streamlit CSS
export const NOTE_TYPE_VARIANTS: Record<string, string> = {
  FEATURE: "feature",
  FIX: "fix",
  BREAKING_CHANGE: "breaking",
  DEPRECATION: "deprecation",
  ISSUE: "issue",
  ANNOUNCEMENT: "announcement",
};

export function badgeVariant(type: string): string {
  return NOTE_TYPE_VARIANTS[type?.toUpperCase()] ?? "default";
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function truncate(text: string, maxLen = 280): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + "…";
}

// Strip HTML tags left in descriptions
export function stripHtml(html: string): string {
  return html.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").trim();
}
