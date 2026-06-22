"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Badge from "@/components/Badge";
import { getReleaseNotes, getFilterOptions, postAIChat, type ReleaseNote, type FilterOptions } from "@/lib/api";
import { stripHtml, formatDate } from "@/lib/utils";
import styles from "./ExploreClient.module.css";

const PAGE_SIZE = 20;
const ALL_TYPES = ["FEATURE", "FIX", "BREAKING_CHANGE", "DEPRECATION", "ISSUE", "ANNOUNCEMENT"];

// ── SVG Icons ──────────────────────────────────────────────────
const BookmarkIcon = ({ active }: { active?: boolean }) => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "inline-block", verticalAlign: "middle" }}>
    <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
  </svg>
);

const ShareIcon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "inline-block", verticalAlign: "middle" }}>
    <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8M16 6l-4-4-4 4M12 2v13" />
  </svg>
);

const LinkedInIcon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" style={{ display: "inline-block", verticalAlign: "middle" }}>
    <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
  </svg>
);

const XIcon = () => (
  <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor" style={{ display: "inline-block", verticalAlign: "middle" }}>
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
  </svg>
);

const EmailIcon = () => (
  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "inline-block", verticalAlign: "middle" }}>
    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
    <polyline points="22,6 12,13 2,6" />
  </svg>
);

// ── Stack helpers (persisted to localStorage) ──────────────────
function loadStack(): string[] {
  try { return JSON.parse(localStorage.getItem("stack") ?? "[]"); }
  catch { return []; }
}
function persistStack(s: string[]) {
  localStorage.setItem("stack", JSON.stringify(s));
}

// ── Bookmarks helpers (persisted to localStorage) ──────────────
function loadBookmarks(): ReleaseNote[] {
  try { return JSON.parse(localStorage.getItem("bookmarks") ?? "[]"); }
  catch { return []; }
}
function persistBookmarks(b: ReleaseNote[]) {
  localStorage.setItem("bookmarks", JSON.stringify(b));
}

export default function ExploreClient() {
  const router       = useRouter();
  const searchParams = useSearchParams();

  // Filters (URL-synced)
  const [search,    setSearch]    = useState(() => searchParams.get("q") ?? "");
  const [types,     setTypes]     = useState<string[]>(() => searchParams.getAll("type"));
  const [startDate, setStartDate] = useState(() => searchParams.get("from") ?? "");
  const [endDate,   setEndDate]   = useState(() => searchParams.get("to") ?? "");
  const [page,      setPage]      = useState(1);

  // Data
  const [filterOpts, setFilterOpts] = useState<FilterOptions | null>(null);
  const [notes,      setNotes]      = useState<ReleaseNote[]>([]);
  const [total,      setTotal]      = useState(0);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState("");

  // Stack: explicit list of product names the user cares about
  const [stack,      setStack]      = useState<string[]>([]);
  const [stackOnly,  setStackOnly]  = useState(false);
  // Product picker state (separate from the stack)
  const [pickerVal,  setPickerVal]  = useState("");

  // Bookmarks
  const [bookmarks,     setBookmarks]     = useState<ReleaseNote[]>([]);
  const [showBookmarks, setShowBookmarks] = useState(false);

  // Share modal states
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [shareNotes,     setShareNotes]     = useState<ReleaseNote[]>([]);
  const [sharePlatform,  setSharePlatform]  = useState<"linkedin" | "x" | "email">("linkedin");
  const [shareTone,      setShareTone]      = useState<"professional" | "technical" | "hype" | "concise">("professional");
  const [shareInstruct,  setShareInstruct]  = useState("");
  const [shareGenerated, setShareGenerated] = useState("");
  const [shareLoading,   setShareLoading]   = useState(false);
  const [shareError,     setShareError]     = useState("");
  const [shareCopied,    setShareCopied]    = useState(false);

  // Share Selection
  const [shareSelection, setShareSelection] = useState<ReleaseNote[]>([]);

  useEffect(() => {
    setStack(loadStack());
    setBookmarks(loadBookmarks());
  }, []);

  function addToStack(product: string) {
    if (!product || stack.includes(product)) return;
    const next = [...stack, product];
    setStack(next);
    persistStack(next);
    setPickerVal("");
  }

  function removeFromStack(product: string) {
    const next = stack.filter(p => p !== product);
    setStack(next);
    persistStack(next);
    if (next.length === 0) setStackOnly(false);
  }

  function toggleBookmark(note: ReleaseNote) {
    const isBookmarked = bookmarks.some(b => 
      b.product_name === note.product_name && 
      b.published_at === note.published_at && 
      b.description === note.description
    );
    let next;
    if (isBookmarked) {
      next = bookmarks.filter(b => 
        !(b.product_name === note.product_name && 
          b.published_at === note.published_at && 
          b.description === note.description)
      );
    } else {
      next = [...bookmarks, note];
    }
    setBookmarks(next);
    persistBookmarks(next);
  }

  const isBookmarked = (note: ReleaseNote) => bookmarks.some(b => 
    b.product_name === note.product_name && 
    b.published_at === note.published_at && 
    b.description === note.description
  );

  function toggleShareSelection(note: ReleaseNote) {
    const isSelected = shareSelection.some(n => 
      n.product_name === note.product_name && 
      n.published_at === note.published_at && 
      n.description === note.description
    );
    let next;
    if (isSelected) {
      next = shareSelection.filter(n => 
        !(n.product_name === note.product_name && 
          n.published_at === note.published_at && 
          n.description === note.description)
      );
    } else {
      next = [...shareSelection, note];
    }
    setShareSelection(next);
  }

  const isShareSelected = (note: ReleaseNote) => shareSelection.some(n => 
    n.product_name === note.product_name && 
    n.published_at === note.published_at && 
    n.description === note.description
  );

  // Load filter options once
  useEffect(() => {
    getFilterOptions().then(setFilterOpts).catch(() => {});
  }, []);

  // Sync URL params
  const pushUrl = useCallback((overrides: Record<string, string | string[]> = {}) => {
    const p  = new URLSearchParams();
    const s  = overrides.q    !== undefined ? String(overrides.q)         : search;
    const ty = overrides.type !== undefined ? (overrides.type as string[]) : types;
    const fr = overrides.from !== undefined ? String(overrides.from)       : startDate;
    const to = overrides.to   !== undefined ? String(overrides.to)         : endDate;
    if (s)  p.set("q", s);
    ty.forEach(t => p.append("type", t));
    if (fr) p.set("from", fr);
    if (to) p.set("to", to);
    router.replace(`/explore?${p.toString()}`, { scroll: false });
  }, [router, search, types, startDate, endDate]);

  // Fetch notes with debounce
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchNotes = useCallback((pg = 1) => {
    if (showBookmarks) {
      setPage(pg);
      return;
    }
    setLoading(true);
    setError("");
    const products = stackOnly && stack.length > 0 ? stack : [];
    getReleaseNotes({
      search,
      types,
      products,
      start_date: startDate || undefined,
      end_date:   endDate   || undefined,
      page:       pg,
      page_size:  PAGE_SIZE,
    })
      .then(({ data, total }) => { setNotes(data); setTotal(total); setPage(pg); })
      .catch(() => setError("Failed to load release notes. Is the backend running?"))
      .finally(() => setLoading(false));
  }, [search, types, startDate, endDate, stack, stackOnly, showBookmarks]);

  useEffect(() => {
    if (showBookmarks) {
      setPage(1);
    } else {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => fetchNotes(1), 350);
      return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, types, startDate, endDate, stackOnly, stack, showBookmarks]);

  function handleSearch(v: string) { setSearch(v); pushUrl({ q: v }); }
  function toggleType(t: string) {
    const next = types.includes(t) ? types.filter(x => x !== t) : [...types, t];
    setTypes(next); pushUrl({ type: next });
  }
  function clearAll() {
    setSearch(""); setTypes([]); setStartDate(""); setEndDate(""); setStackOnly(false);
    router.replace("/explore", { scroll: false });
  }

  // Filter bookmarks locally in memory
  const displayedNotes = showBookmarks 
    ? bookmarks.filter(note => {
        if (search && !note.description.toLowerCase().includes(search.toLowerCase()) && !note.product_name.toLowerCase().includes(search.toLowerCase())) return false;
        if (types.length && !types.includes(note.release_note_type)) return false;
        if (stackOnly && stack.length && !stack.includes(note.product_name)) return false;
        if (startDate && note.published_at < startDate) return false;
        if (endDate && note.published_at > endDate) return false;
        return true;
      })
    : notes;

  const totalDisplayed = showBookmarks ? displayedNotes.length : total;
  const totalPages = showBookmarks ? Math.ceil(totalDisplayed / PAGE_SIZE) : Math.ceil(total / PAGE_SIZE);

  // Paginate bookmarks in-memory
  const paginatedNotes = showBookmarks 
    ? displayedNotes.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
    : notes;

  const hasFilters = search || types.length || startDate || endDate || stackOnly;

  // Products not yet in stack (for picker)
  const availableProducts = filterOpts?.products.filter(p => !stack.includes(p)) ?? [];

  async function generateSharePost() {
    if (shareNotes.length === 0) {
      setShareError("Please select at least one release note.");
      return;
    }
    setShareLoading(true);
    setShareError("");
    setShareCopied(false);

    const notesStr = shareNotes.map((n, i) => 
      `Note ${i + 1}: [${n.release_note_type}] ${n.product_name} (${formatDate(n.published_at)})\n${stripHtml(n.description)}`
    ).join("\n\n");

    const prompt = `Write a ${sharePlatform === "x" ? "Twitter/X post" : sharePlatform === "linkedin" ? "LinkedIn post" : "short email summary newsletter"} about these release updates.
Use a ${shareTone} tone. Keep it highly readable and clean. ${sharePlatform === "x" ? "The output MUST be strictly under 280 characters in total (absolute limit)." : "Use bullet points."}
Do NOT use any emojis in the generated text. ${shareInstruct ? `Additional instructions: ${shareInstruct}` : ""}
Here are the release notes to summarize:
${notesStr}

Provide ONLY the final generated social post text. No introductory remarks like "Here is your post:".`;

    try {
      const res = await postAIChat({
        question: prompt,
        products: shareNotes.map(n => n.product_name),
      });
      setShareGenerated(res.answer);
    } catch (err: any) {
      setShareError(err?.message || "Failed to generate post. Make sure the backend is running.");
    } finally {
      setShareLoading(false);
    }
  }

  function handleShareCopy() {
    navigator.clipboard.writeText(shareGenerated);
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2000);
  }

  function handleSharePostDirect() {
    if (!shareGenerated) return;
    if (sharePlatform === "x") {
      const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareGenerated)}`;
      window.open(url, "_blank", "noopener,noreferrer");
    } else if (sharePlatform === "linkedin") {
      window.open("https://www.linkedin.com/sharing/share-offsite/", "_blank", "noopener,noreferrer");
    } else if (sharePlatform === "email") {
      const subject = encodeURIComponent("Cloud News & Updates Summary");
      const url = `mailto:?subject=${subject}&body=${encodeURIComponent(shareGenerated)}`;
      window.open(url, "_self");
    }
  }

  return (
    <div className={styles.page}>

      {/* ── Your Stack ──────────────────────────────────────────── */}
      <section className={styles.stackSection}>
        <div className={styles.stackHeader}>
          <span className={styles.stackLabel}>Your stack</span>
          {stack.length > 0 && (
            <button
              className={`${styles.stackFilterBtn} ${stackOnly ? styles.stackFilterActive : ""}`}
              onClick={() => setStackOnly(v => !v)}
            >
              {stackOnly ? "Showing stack only" : "Filter to stack"}
            </button>
          )}
        </div>

        <div className={styles.stackBody}>
          {/* Saved product chips */}
          {stack.length === 0 && (
            <span className={styles.stackEmpty}>
              Add GCP products you care about — they'll be saved here.
            </span>
          )}
          {stack.map(p => (
            <span key={p} className={styles.stackChip}>
              {p}
              <button
                className={styles.stackChipRemove}
                onClick={() => removeFromStack(p)}
                aria-label={`Remove ${p} from stack`}
              >
                ×
              </button>
            </span>
          ))}

          {/* Product picker */}
          <select
            className={styles.stackPicker}
            value={pickerVal}
            onChange={e => addToStack(e.target.value)}
            aria-label="Add a product to your stack"
          >
            <option value="">+ Add product…</option>
            {availableProducts.map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
      </section>

      {/* ── Page header ─────────────────────────────────────────── */}
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.title}>{showBookmarks ? "Saved Notes" : "Explore"}</h1>
          {showBookmarks ? (
            <p className={styles.count}>
              {totalDisplayed.toLocaleString()} saved {totalDisplayed === 1 ? "note" : "notes"}
              {hasFilters ? " matching filters" : ""}
            </p>
          ) : (
            !loading && (
              <p className={styles.count}>
                {total.toLocaleString()} {total === 1 ? "note" : "notes"}
                {hasFilters ? " matching filters" : ""}
              </p>
            )
          )}
        </div>
        <div className={styles.headerActions}>
          <button
            className={`${styles.bookmarksToggleBtn} ${showBookmarks ? styles.bookmarksActive : ""}`}
            onClick={() => setShowBookmarks(!showBookmarks)}
            style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
          >
            <BookmarkIcon active={showBookmarks} />
            {showBookmarks ? "Show all release notes" : "Saved notes"}
          </button>
          {shareSelection.length > 0 && (
            <button
              className={styles.shareToggleBtn}
              onClick={() => {
                setShareNotes([...shareSelection]);
                setShareModalOpen(true);
                setShareGenerated("");
                setShareError("");
                setShareInstruct("");
              }}
              style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
            >
              <ShareIcon />
              Share selection ({shareSelection.length})
            </button>
          )}
        </div>
      </div>

      {/* ── Search ──────────────────────────────────────────────── */}
      <div className={styles.searchRow}>
        <input
          id="explore-search"
          type="search"
          className={styles.searchInput}
          placeholder={showBookmarks ? "Search saved notes…" : "Search release notes…"}
          value={search}
          onChange={e => handleSearch(e.target.value)}
          aria-label="Search release notes"
        />
      </div>

      {/* ── Filters ─────────────────────────────────────────────── */}
      <div className={styles.filters}>
        <div className={styles.chips}>
          {ALL_TYPES.map(t => (
            <button
              key={t}
              className={`${styles.chip} ${types.includes(t) ? styles.chipActive : ""}`}
              onClick={() => toggleType(t)}
            >
              {t.replace(/_/g, " ").toLowerCase()}
            </button>
          ))}
        </div>

        <div className={styles.filterRow}>
          <input type="date" className={styles.dateInput} value={startDate}
            onChange={e => { setStartDate(e.target.value); pushUrl({ from: e.target.value }); }}
            aria-label="From date" max={endDate || undefined}
          />
          <span className={styles.dateSep}>→</span>
          <input type="date" className={styles.dateInput} value={endDate}
            onChange={e => { setEndDate(e.target.value); pushUrl({ to: e.target.value }); }}
            aria-label="To date" min={startDate || undefined}
          />
          {hasFilters && (
            <button className={styles.clearBtn} onClick={clearAll}>Clear filters</button>
          )}
        </div>
      </div>

      {/* ── Results ─────────────────────────────────────────────── */}
      {error && <p className={styles.error}>{error}</p>}

      {loading && !showBookmarks ? (
        <ul className={styles.list}>
          {Array.from({ length: 8 }).map((_, i) => (
            <li key={i} className={styles.skeleton} aria-hidden />
          ))}
        </ul>
      ) : paginatedNotes.length === 0 ? (
        <div className={styles.empty}>
          <p>{showBookmarks ? "No saved notes found." : "No release notes found."}</p>
          {hasFilters && <button className={styles.clearBtn} onClick={clearAll}>Clear filters</button>}
        </div>
      ) : (
        <ul className={styles.list}>
          {paginatedNotes.map((note, i) => (
            <NoteRow 
              key={i} 
              note={note} 
              isBookmarked={isBookmarked(note)}
              onToggleBookmark={() => toggleBookmark(note)}
              isShareSelected={isShareSelected(note)}
              onToggleShare={() => toggleShareSelection(note)}
            />
          ))}
        </ul>
      )}

      {/* ── Pagination ──────────────────────────────────────────── */}
      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button className={styles.pageBtn} onClick={() => fetchNotes(page - 1)} disabled={page <= 1}>
            ← Prev
          </button>
          <span className={styles.pageInfo}>Page {page} of {totalPages.toLocaleString()}</span>
          <button className={styles.pageBtn} onClick={() => fetchNotes(page + 1)} disabled={page >= totalPages}>
            Next →
          </button>
        </div>
      )}

      {/* ── Share Modal ────────────────────────────────────────── */}
      {shareModalOpen && (
        <div className={styles.modalOverlay} onClick={() => setShareModalOpen(false)}>
          <div className={styles.modalContent} onClick={e => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div>
                <h2 style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
                  <ShareIcon /> Share updates
                </h2>
                <p className={styles.modalSubtitle}>Format and publish your selected release updates.</p>
              </div>
              <button className={styles.modalClose} onClick={() => setShareModalOpen(false)}>×</button>
            </div>

            <div className={styles.modalBody}>
              {/* Left Side: Selected Notes list with checkboxes to toggle share status */}
              <div className={styles.modalLeft}>
                <div className={styles.modalSectionTitle}>
                  <span>Select Updates ({shareNotes.length})</span>
                </div>
                <ul className={styles.modalNotesList}>
                  {shareSelection.map((note, index) => {
                    const isSelected = shareNotes.some(n => 
                      n.product_name === note.product_name && 
                      n.published_at === note.published_at && 
                      n.description === note.description
                    );
                    return (
                      <li 
                        key={index}
                        className={`${styles.modalNoteItem} ${isSelected ? styles.modalNoteSelected : ""}`}
                        onClick={() => {
                          if (isSelected) {
                            setShareNotes(prev => prev.filter(n => 
                              !(n.product_name === note.product_name && 
                                n.published_at === note.published_at && 
                                n.description === note.description)
                            ));
                          } else {
                            setShareNotes(prev => [...prev, note]);
                          }
                        }}
                      >
                        <input 
                          type="checkbox" 
                          checked={isSelected}
                          onChange={() => {}}
                          className={styles.modalCheckbox}
                        />
                        <div className={styles.modalNoteMeta}>
                          <span className={styles.modalProduct}>{note.product_name}</span>
                          <span className={styles.modalDate}>{formatDate(note.published_at)}</span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>

              {/* Right Side: Options & Results */}
              <div className={styles.modalRight}>
                <div className={styles.formGroup}>
                  <label className={styles.fieldLabel}>Platform Format</label>
                  <div className={styles.platformSelector}>
                    <button 
                      className={`${styles.platformBtn} ${sharePlatform === "linkedin" ? styles.platformActive : ""}`}
                      onClick={() => setSharePlatform("linkedin")}
                      style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "6px" }}
                    >
                      <LinkedInIcon /> LinkedIn
                    </button>
                    <button 
                      className={`${styles.platformBtn} ${sharePlatform === "x" ? styles.platformActive : ""}`}
                      onClick={() => setSharePlatform("x")}
                      style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "6px" }}
                    >
                      <XIcon /> X (Twitter)
                    </button>
                    <button 
                      className={`${styles.platformBtn} ${sharePlatform === "email" ? styles.platformActive : ""}`}
                      onClick={() => setSharePlatform("email")}
                      style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "6px" }}
                    >
                      <EmailIcon /> Email
                    </button>
                  </div>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.fieldLabel}>Tone of voice</label>
                  <div className={styles.toneSelector}>
                    {[
                      { id: "professional", label: "Professional" },
                      { id: "technical", label: "Technical" },
                      { id: "hype", label: "Engaging" },
                      { id: "concise", label: "Concise" }
                    ].map(t => (
                      <button
                        key={t.id}
                        className={`${styles.toneChip} ${shareTone === t.id ? styles.toneChipActive : ""}`}
                        onClick={() => setShareTone(t.id as any)}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.fieldLabel}>Custom Prompt (Optional)</label>
                  <input
                    type="text"
                    className={styles.modalInput}
                    placeholder="e.g. emphasize developer tools, add hashtags..."
                    value={shareInstruct}
                    onChange={e => setShareInstruct(e.target.value)}
                  />
                </div>

                <button 
                  className={styles.modalGenerateBtn}
                  onClick={generateSharePost}
                  disabled={shareLoading || shareNotes.length === 0}
                >
                  {shareLoading ? "Generating..." : "Generate Social Post"}
                </button>

                {shareError && <p className={styles.modalError}>{shareError}</p>}

                {shareGenerated && (
                  <div className={styles.draftSection}>
                    <div className={styles.draftHeader}>
                      <span>
                        Generated Draft
                        {sharePlatform === "x" && (
                          <span style={{ marginLeft: "8px", fontWeight: "normal", color: shareGenerated.length > 280 ? "#dc2626" : "var(--text-3)" }}>
                            ({shareGenerated.length}/280)
                          </span>
                        )}
                      </span>
                      <div className={styles.draftActions}>
                        <button className={styles.copyBtn} onClick={handleShareCopy}>
                          {shareCopied ? "Copied!" : "Copy"}
                        </button>
                        <button className={styles.postBtn} onClick={handleSharePostDirect}>
                          {sharePlatform === "x" ? "Post to X" : sharePlatform === "linkedin" ? "LinkedIn" : "Email"}
                        </button>
                      </div>
                    </div>
                    <textarea
                      className={styles.draftTextArea}
                      value={shareGenerated}
                      onChange={e => setShareGenerated(e.target.value)}
                      rows={6}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating Action Bar for sharing */}
      {shareSelection.length > 0 && (
        <div className={styles.floatingActionBar}>
          <div className={styles.floatingActionBarInner}>
            <span>{shareSelection.length} {shareSelection.length === 1 ? "note" : "notes"} selected for sharing</span>
            <div className={styles.floatingActionBarBtns}>
              <button className={styles.clearSelectionBtn} onClick={() => setShareSelection([])}>
                Clear
              </button>
              <button 
                className={styles.floatingShareBtn} 
                onClick={() => {
                  setShareNotes([...shareSelection]);
                  setShareModalOpen(true);
                  setShareGenerated("");
                  setShareError("");
                  setShareInstruct("");
                }}
              >
                <ShareIcon /> Share selected
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Note row ───────────────────────────────────────────────────
function NoteRow({ 
  note, 
  isBookmarked, 
  onToggleBookmark,
  isShareSelected,
  onToggleShare
}: { 
  note: ReleaseNote; 
  isBookmarked: boolean; 
  onToggleBookmark: () => void;
  isShareSelected: boolean;
  onToggleShare: () => void;
}) {
  return (
    <li className={styles.noteRow}>
      <div className={styles.noteMeta}>
        <span className={styles.noteProduct}>{note.product_name}</span>
        <Badge type={note.release_note_type} />
        <time className={styles.noteDate} dateTime={note.published_at}>
          {formatDate(note.published_at)}
        </time>
        <button 
          className={`${styles.bookmarkBtn} ${isBookmarked ? styles.bookmarked : ""}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggleBookmark();
          }}
          style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}
          aria-label={isBookmarked ? "Remove bookmark" : "Bookmark note"}
        >
          <BookmarkIcon active={isBookmarked} />
          {isBookmarked ? "Saved" : "Save note"}
        </button>

        <button 
          className={`${styles.shareBtn} ${isShareSelected ? styles.shareSelected : ""}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggleShare();
          }}
          style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}
          aria-label={isShareSelected ? "Remove from share selection" : "Select to share"}
        >
          <ShareIcon />
          {isShareSelected ? "Selected to share" : "Share"}
        </button>
      </div>
      <div 
        className={styles.noteDesc}
        dangerouslySetInnerHTML={{ __html: note.description }}
      />
    </li>
  );
}
