"use client";

import { useEffect, useState } from "react";
import { getReleaseNotes, postAIChat, type ReleaseNote } from "@/lib/api";
import { stripHtml, formatDate } from "@/lib/utils";
import styles from "./page.module.css";

type Platform = "x" | "linkedin" | "email";
type Tone = "professional" | "technical" | "hype" | "concise";

export default function SharePage() {
  const [bookmarks, setBookmarks] = useState<ReleaseNote[]>([]);
  const [selectedNotes, setSelectedNotes] = useState<ReleaseNote[]>([]);
  const [platform, setPlatform] = useState<Platform>("linkedin");
  const [tone, setTone] = useState<Tone>("professional");
  const [generatedText, setGeneratedText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  // Load bookmarks (default items to share)
  useEffect(() => {
    try {
      const saved: ReleaseNote[] = JSON.parse(localStorage.getItem("bookmarks") ?? "[]");
      setBookmarks(saved);
      // Auto-select all bookmarks initially
      setSelectedNotes(saved);
    } catch {
      setBookmarks([]);
    }
  }, []);

  function toggleSelectNote(note: ReleaseNote) {
    const isSelected = selectedNotes.some(n => 
      n.product_name === note.product_name && 
      n.published_at === note.published_at && 
      n.description === note.description
    );
    if (isSelected) {
      setSelectedNotes(prev => prev.filter(n => 
        !(n.product_name === note.product_name && 
          n.published_at === note.published_at && 
          n.description === note.description)
      ));
    } else {
      setSelectedNotes(prev => [...prev, note]);
    }
  }

  function handleSelectAll() {
    if (selectedNotes.length === bookmarks.length) {
      setSelectedNotes([]);
    } else {
      setSelectedNotes([...bookmarks]);
    }
  }

  async function handleGenerate() {
    if (selectedNotes.length === 0) {
      setError("Please select at least one release note to generate a post.");
      return;
    }
    setLoading(true);
    setError("");
    setCopied(false);

    // Format selected notes for the prompt context
    const notesStr = selectedNotes.map((n, i) => 
      `Note ${i + 1}: [${n.release_note_type}] ${n.product_name} (${formatDate(n.published_at)})\n${stripHtml(n.description)}`
    ).join("\n\n");

    const prompt = `Write a ${platform === "x" ? "Twitter/X post (or thread if long)" : platform === "linkedin" ? "LinkedIn post" : "short email summary newsletter"} about these release updates.
Use a ${tone} tone. Keep it highly readable, clean, use bullet points, and add relevant emojis but don't overdo them.
Here are the release notes to summarize:
${notesStr}

Provide ONLY the final generated social post text. No introductory remarks like "Here is your post:".`;

    try {
      // We pass the prompt as the question and let the API synthesize the updates
      const res = await postAIChat({
        question: prompt,
        products: selectedNotes.map(n => n.product_name),
      });
      setGeneratedText(res.answer);
    } catch (err: any) {
      setError(err?.message || "Failed to generate social post. Please ensure the backend is running.");
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(generatedText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handlePost() {
    if (!generatedText) return;
    if (platform === "x") {
      const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(generatedText)}`;
      window.open(url, "_blank", "noopener,noreferrer");
    } else if (platform === "linkedin") {
      // LinkedIn share intent doesn't support pre-filled text in the free URL intent, 
      // but opening the share page lets them paste the copied clipboard text.
      window.open("https://www.linkedin.com/sharing/share-offsite/", "_blank", "noopener,noreferrer");
    } else if (platform === "email") {
      const subject = encodeURIComponent("Cloud News & Updates Summary");
      const url = `mailto:?subject=${subject}&body=${encodeURIComponent(generatedText)}`;
      window.open(url, "_self");
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Share updates</h1>
          <p className={styles.subtitle}>Format and publish release notes directly to social media using AI.</p>
        </div>
      </div>

      <div className={styles.layout}>
        {/* Left Column: Notes selection */}
        <div className={styles.leftCol}>
          <div className={styles.panelHeader}>
            <h3>Select Notes ({selectedNotes.length})</h3>
            {bookmarks.length > 0 && (
              <button className={styles.textLink} onClick={handleSelectAll}>
                {selectedNotes.length === bookmarks.length ? "Deselect All" : "Select All"}
              </button>
            )}
          </div>

          {bookmarks.length === 0 ? (
            <div className={styles.emptyBookmarks}>
              <p>No saved notes to share.</p>
              <p className={styles.emptyTip}>
                Go to the <a href="/explore">Explore</a> tab and click the bookmark button (🔖) on release notes you want to compile and share.
              </p>
            </div>
          ) : (
            <ul className={styles.bookmarksList}>
              {bookmarks.map((note, index) => {
                const isSelected = selectedNotes.some(n => 
                  n.product_name === note.product_name && 
                  n.published_at === note.published_at && 
                  n.description === note.description
                );
                return (
                  <li 
                    key={index} 
                    className={`${styles.noteItem} ${isSelected ? styles.noteSelected : ""}`}
                    onClick={() => toggleSelectNote(note)}
                  >
                    <div className={styles.noteCheckbox}>
                      <input 
                        type="checkbox" 
                        checked={isSelected}
                        onChange={() => {}} // Handled by list row click
                        aria-label="Select note to share"
                      />
                    </div>
                    <div className={styles.noteText}>
                      <div className={styles.noteMeta}>
                        <span className={styles.noteProduct}>{note.product_name}</span>
                        <span className={styles.noteDate}>{formatDate(note.published_at)}</span>
                      </div>
                      <p className={styles.noteDesc}>{stripHtml(note.description)}</p>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Right Column: AI social post options & results */}
        <div className={styles.rightCol}>
          <div className={styles.optionsPanel}>
            <h3>AI Generator Settings</h3>
            
            <div className={styles.formGroup}>
              <label className={styles.fieldLabel}>Platform Format</label>
              <div className={styles.buttonGroup}>
                <button 
                  className={`${styles.optionBtn} ${platform === "linkedin" ? styles.optionActive : ""}`}
                  onClick={() => setPlatform("linkedin")}
                >
                  💼 LinkedIn
                </button>
                <button 
                  className={`${styles.optionBtn} ${platform === "x" ? styles.optionActive : ""}`}
                  onClick={() => setPlatform("x")}
                >
                  🐦 X (Twitter)
                </button>
                <button 
                  className={`${styles.optionBtn} ${platform === "email" ? styles.optionActive : ""}`}
                  onClick={() => setPlatform("email")}
                >
                  ✉ Email
                </button>
              </div>
            </div>

            <div className={styles.formGroup}>
              <label className={styles.fieldLabel}>Tone of Voice</label>
              <div className={styles.toneGrid}>
                {[
                  { id: "professional", label: "💼 Professional", desc: "For business & tech leaders" },
                  { id: "technical", label: "💻 Technical", desc: "Detailed with code/specs" },
                  { id: "hype", label: "🚀 Exciting", desc: "Highlighting innovation" },
                  { id: "concise", label: "⚡ Bullet points", desc: "Just the facts, fast" }
                ].map(t => (
                  <button 
                    key={t.id}
                    className={`${styles.toneBtn} ${tone === t.id ? styles.toneActive : ""}`}
                    onClick={() => setTone(t.id as Tone)}
                  >
                    <span className={styles.toneLabel}>{t.label}</span>
                    <span className={styles.toneDesc}>{t.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            <button 
              className={styles.generateBtn} 
              onClick={handleGenerate}
              disabled={loading || selectedNotes.length === 0}
            >
              {loading ? "Generating post..." : `✨ Generate ${platform === "x" ? "X Post" : platform === "linkedin" ? "LinkedIn Post" : "Email"}`}
            </button>

            {error && <p className={styles.error}>{error}</p>}
          </div>

          {/* Generated Result Output */}
          {generatedText && (
            <div className={styles.resultPanel}>
              <div className={styles.resultHeader}>
                <h3>AI Result Draft</h3>
                <div className={styles.actionRow}>
                  <button className={styles.copyBtn} onClick={handleCopy}>
                    {copied ? "✓ Copied" : "Copy text"}
                  </button>
                  <button className={styles.postBtn} onClick={handlePost}>
                    {platform === "x" ? "Post to X ↗" : platform === "linkedin" ? "Go to LinkedIn ↗" : "Compose email ↗"}
                  </button>
                </div>
              </div>
              <textarea 
                className={styles.resultTextArea}
                value={generatedText}
                onChange={e => setGeneratedText(e.target.value)}
                rows={12}
                aria-label="Generated social media post content"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
