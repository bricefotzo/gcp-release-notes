"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Badge from "@/components/Badge";
import { getReleaseNotes, getFilterOptions, type ReleaseNote, type FilterOptions } from "@/lib/api";
import { stripHtml, formatDate } from "@/lib/utils";
import styles from "./ExploreClient.module.css";

const PAGE_SIZE = 20;
const ALL_TYPES = ["FEATURE", "FIX", "BREAKING_CHANGE", "DEPRECATION", "ISSUE", "ANNOUNCEMENT"];

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
        <button
          className={`${styles.bookmarksToggleBtn} ${showBookmarks ? styles.bookmarksActive : ""}`}
          onClick={() => setShowBookmarks(!showBookmarks)}
        >
          {showBookmarks ? "Show all release notes" : "🔖 View saved notes"}
        </button>
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
    </div>
  );
}

// ── Note row ───────────────────────────────────────────────────
function NoteRow({ 
  note, 
  isBookmarked, 
  onToggleBookmark 
}: { 
  note: ReleaseNote; 
  isBookmarked: boolean; 
  onToggleBookmark: () => void; 
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
          aria-label={isBookmarked ? "Remove bookmark" : "Bookmark note"}
        >
          {isBookmarked ? "🔖 Saved" : "bookmark"}
        </button>
      </div>
      <p className={styles.noteDesc}>{stripHtml(note.description)}</p>
    </li>
  );
}
