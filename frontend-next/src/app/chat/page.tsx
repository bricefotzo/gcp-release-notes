"use client";

import { useEffect, useState, useRef } from "react";
import { getFilterOptions, postAIChat, postAIQuery, type FilterOptions, type ReleaseNote } from "@/lib/api";
import styles from "./page.module.css";

type Mode = "chat" | "sql";

const ALL_TYPES = ["FEATURE", "FIX", "BREAKING_CHANGE", "DEPRECATION", "ISSUE", "ANNOUNCEMENT"];

type Message = {
  id: string;
  sender: "user" | "ai";
  text: string;
  sql?: string;
  rows?: Record<string, any>[];
  count?: number;
  total?: number;
};

const SUGGESTIONS = {
  chat: [
    "What are the major updates for BigQuery this month?",
    "Summarize recent Cloud Storage deprecations.",
    "Tell me about any networking security announcements.",
  ],
  sql: [
    "Which product has the highest count of release notes?",
    "How many BREAKING_CHANGE release notes were published in 2024?",
    "Show the 5 most recent compute engine release notes.",
  ],
};

export default function ChatPage() {
  const [mode, setMode] = useState<Mode>("chat");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Filters for Chat mode
  const [filterOpts, setFilterOpts] = useState<FilterOptions | null>(null);
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [useStack, setUseStack] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load GCP filter options
  useEffect(() => {
    getFilterOptions().then(setFilterOpts).catch(() => {});
  }, []);

  // Handle stack load when checkbox clicked
  useEffect(() => {
    if (useStack) {
      try {
        const stack: string[] = JSON.parse(localStorage.getItem("stack") ?? "[]");
        setSelectedProducts(stack);
      } catch {
        setSelectedProducts([]);
      }
    } else {
      setSelectedProducts([]);
    }
  }, [useStack]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(textToSend = question) {
    if (!textToSend.trim() || loading) return;
    setLoading(true);
    setError("");

    const userMsg: Message = {
      id: Math.random().toString(),
      sender: "user",
      text: textToSend,
    };
    setMessages(prev => [...prev, userMsg]);
    if (textToSend === question) setQuestion("");

    try {
      if (mode === "chat") {
        const res = await postAIChat({
          question: textToSend,
          products: selectedProducts,
          types: selectedTypes,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
        });

        const aiMsg: Message = {
          id: Math.random().toString(),
          sender: "ai",
          text: res.answer,
          count: res.count,
          total: res.total,
        };
        setMessages(prev => [...prev, aiMsg]);
      } else {
        const res = await postAIQuery(textToSend);

        const aiMsg: Message = {
          id: Math.random().toString(),
          sender: "ai",
          text: `I executed a BigQuery query to fetch the results.`,
          sql: res.sql,
          rows: res.rows,
          total: res.total,
        };
        setMessages(prev => [...prev, aiMsg]);
      }
    } catch (err: any) {
      setError(err?.message || "AI failed to respond. Please check that the server is online.");
      // Remove last user message so they can retry easily if they want
    } finally {
      setLoading(false);
    }
  }

  function handleSuggestionClick(sug: string) {
    handleSend(sug);
  }

  function clearHistory() {
    setMessages([]);
    setError("");
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Ask AI</h1>
          <p className={styles.subtitle}>Ask questions or query release log history in natural language.</p>
        </div>
        {messages.length > 0 && (
          <button className={styles.clearBtn} onClick={clearHistory}>Clear chat</button>
        )}
      </div>

      {/* Mode Switcher */}
      <div className={styles.modeTabs}>
        <button
          className={`${styles.tab} ${mode === "chat" ? styles.activeTab : ""}`}
          onClick={() => { setMode("chat"); setError(""); }}
        >
          💡 Explain Notes
        </button>
        <button
          className={`${styles.tab} ${mode === "sql" ? styles.activeTab : ""}`}
          onClick={() => { setMode("sql"); setError(""); }}
        >
          ⚙ BigQuery SQL Query
        </button>
      </div>

      <div className={styles.layout}>
        {/* Main Chat Feed */}
        <div className={styles.chatSection}>
          {messages.length === 0 ? (
            <div className={styles.welcome}>
              <div className={styles.welcomeIcon}>{mode === "chat" ? "💡" : "⚙"}</div>
              <h2>{mode === "chat" ? "Summarize & Explain" : "Natural Language to SQL"}</h2>
              <p>
                {mode === "chat"
                  ? "Ask questions about the release notes. The AI will read the matching notes and summarize the updates in friendly language."
                  : "Ask a data question. The AI will translate it into a SQL query, run it against BigQuery, and display the direct data table."}
              </p>

              <div className={styles.suggestions}>
                <span className={styles.sugLabel}>Try asking:</span>
                <div className={styles.sugGrid}>
                  {SUGGESTIONS[mode].map((sug, idx) => (
                    <button
                      key={idx}
                      className={styles.sugButton}
                      onClick={() => handleSuggestionClick(sug)}
                    >
                      {sug}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className={styles.messageList}>
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`${styles.messageRow} ${msg.sender === "user" ? styles.userRow : styles.aiRow}`}
                >
                  <div className={styles.avatar}>
                    {msg.sender === "user" ? "U" : "AI"}
                  </div>
                  <div className={styles.messageContent}>
                    <p className={styles.messageText}>{msg.text}</p>

                    {/* SQL Result visualization */}
                    {msg.sql && (
                      <div className={styles.sqlWrapper}>
                        <details className={styles.sqlDetails}>
                          <summary className={styles.sqlSummary}>View generated SQL query</summary>
                          <pre className={styles.sqlCode}><code>{msg.sql}</code></pre>
                        </details>
                      </div>
                    )}

                    {/* SQL Table visualization */}
                    {msg.rows && msg.rows.length > 0 && (
                      <div className={styles.tableWrapper}>
                        <table className={styles.resultsTable}>
                          <thead>
                            <tr>
                              {Object.keys(msg.rows[0]).map((key) => (
                                <th key={key}>{key}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {msg.rows.map((row, i) => (
                              <tr key={i}>
                                {Object.values(row).map((val: any, j) => (
                                  <td key={j}>{String(val)}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <span className={styles.tableCount}>
                          Showing {msg.rows.length} of {msg.total ?? msg.rows.length} rows
                        </span>
                      </div>
                    )}
                    
                    {msg.rows && msg.rows.length === 0 && (
                      <div className={styles.emptyTable}>No matching rows returned from BigQuery.</div>
                    )}

                    {/* Chat Context Info */}
                    {msg.count !== undefined && msg.count > 0 && (
                      <span className={styles.contextInfo}>
                        Summarized {msg.count} of {msg.total} matching release notes.
                      </span>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className={`${styles.messageRow} ${styles.aiRow} ${styles.shimmer}`}>
                  <div className={styles.avatar}>AI</div>
                  <div className={styles.messageContent}>
                    <div className={styles.skeletonLine} style={{ width: "80%" }} />
                    <div className={styles.skeletonLine} style={{ width: "60%" }} />
                    <div className={styles.skeletonLine} style={{ width: "90%" }} />
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}

          {error && <div className={styles.error}>{error}</div>}

          {/* Chat Input */}
          <form
            className={styles.inputForm}
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
          >
            <input
              type="text"
              className={styles.chatInput}
              placeholder={mode === "chat" ? "Ask a question about the release notes…" : "Write a data question (e.g. which product had highest volume?)"}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={loading}
              aria-label="Ask AI input"
            />
            <button type="submit" className={styles.sendBtn} disabled={loading || !question.trim()}>
              Ask
            </button>
          </form>
        </div>

        {/* Sidebar Filters (only for Chat Mode) */}
        {mode === "chat" && (
          <aside className={styles.sidebar}>
            <h3 className={styles.sidebarTitle}>Chat Context</h3>
            <p className={styles.sidebarDesc}>
              Restrict the release notes the AI is allowed to read.
            </p>

            <div className={styles.formGroup}>
              <label className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={useStack}
                  onChange={(e) => setUseStack(e.target.checked)}
                />
                Use my product stack
              </label>
            </div>

            {!useStack && filterOpts && (
              <div className={styles.formGroup}>
                <label className={styles.fieldLabel}>Filter Products</label>
                <div className={styles.checkboxGrid}>
                  {filterOpts.products.slice(0, 12).map((p) => {
                    const active = selectedProducts.includes(p);
                    return (
                      <button
                        type="button"
                        key={p}
                        className={`${styles.filterChip} ${active ? styles.filterChipActive : ""}`}
                        onClick={() => {
                          setSelectedProducts(prev =>
                            active ? prev.filter(x => x !== p) : [...prev, p]
                          );
                        }}
                      >
                        {p}
                      </button>
                    );
                  })}
                  {filterOpts.products.length > 12 && (
                    <span className={styles.moreLabel}>
                      + {filterOpts.products.length - 12} more in database
                    </span>
                  )}
                </div>
              </div>
            )}

            <div className={styles.formGroup}>
              <label className={styles.fieldLabel}>Types</label>
              <div className={styles.checkboxGrid}>
                {ALL_TYPES.map((t) => {
                  const active = selectedTypes.includes(t);
                  return (
                    <button
                      type="button"
                      key={t}
                      className={`${styles.filterChip} ${active ? styles.filterChipActive : ""}`}
                      onClick={() => {
                        setSelectedTypes(prev =>
                          active ? prev.filter(x => x !== t) : [...prev, t]
                        );
                      }}
                    >
                      {t.replace(/_/g, " ").toLowerCase()}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className={styles.formGroup}>
              <label className={styles.fieldLabel}>Date Range</label>
              <div className={styles.dateInputs}>
                <input
                  type="date"
                  className={styles.dateInput}
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  aria-label="Start date"
                />
                <span className={styles.dateSep}>→</span>
                <input
                  type="date"
                  className={styles.dateInput}
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  aria-label="End date"
                />
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
