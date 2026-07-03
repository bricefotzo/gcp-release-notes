"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHealth, getFilterOptions, type FilterOptions } from "@/lib/api";
import styles from "./page.module.css";

type Status = "loading" | "ok" | "error";

const ExploreIcon = () => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}>
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </svg>
);

const MorningPaperIcon = () => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}>
    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
    <line x1="16" y1="8" x2="18" y2="8" />
    <line x1="16" y1="12" x2="18" y2="12" />
    <line x1="16" y1="16" x2="18" y2="16" />
    <rect x="6" y="8" width="6" height="8" />
  </svg>
);

const AskAIIcon = () => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "block" }}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const FEATURES = [
  { href: "/explore",       icon: <ExploreIcon />,       title: "Explore",       desc: "Search and filter release notes across every GCP product and note type." },
  { href: "/morning-paper", icon: <MorningPaperIcon />, title: "Morning paper", desc: "A daily briefing on what changed in your stack — readable in 2 minutes." },
  { href: "/chat",          icon: <AskAIIcon />,          title: "Ask AI",        desc: "Chat with the release notes. Ask anything, get grounded answers." },
];

export default function Home() {
  const [healthStatus, setHealthStatus] = useState<Status>("loading");
  const [filters, setFilters] = useState<FilterOptions | null>(null);
  const [filtersStatus, setFiltersStatus] = useState<Status>("loading");

  useEffect(() => {
    getHealth()
      .then(() => setHealthStatus("ok"))
      .catch(() => setHealthStatus("error"));

    getFilterOptions()
      .then((d) => { setFilters(d); setFiltersStatus("ok"); })
      .catch(() => setFiltersStatus("error"));
  }, []);

  const stats = [
    {
      label: "API",
      value: healthStatus === "loading" ? "—" : healthStatus === "ok" ? "Online" : "Offline",
      status: healthStatus,
    },
    {
      label: "Products",
      value: filtersStatus === "loading" ? "—" : filtersStatus === "ok" ? (filters?.products.length ?? 0).toLocaleString() : "—",
      status: filtersStatus,
    },
    {
      label: "Note types",
      value: filtersStatus === "loading" ? "—" : filtersStatus === "ok" ? (filters?.types.length ?? 0) : "—",
      status: filtersStatus,
    },
    {
      label: "Dataset",
      value: filtersStatus === "loading" ? "—" : filtersStatus === "ok" && filters
        ? `${filters.min_date.slice(0,4)}–${filters.max_date.slice(0,4)}`
        : "—",
      status: filtersStatus,
    },
  ];

  return (
    <div className={styles.page}>
      {/* Hero */}
      <section className={styles.hero}>
        <div className={styles.kicker}>
          <span className={styles.kickerDot} />
          Currently tracking: Google Cloud (GCP)
        </div>
        <h1 className={styles.title}>Cloud release notes, made readable.</h1>
        <p className={styles.subtitle}>
          Explore official logs, listen to automated daily summaries, and chat with release history using AI. Built to support multiple platforms.
        </p>
      </section>

      {/* Live stats */}
      <div className={styles.stats}>
        {stats.map(({ label, value, status }) => (
          <div key={label} className={styles.stat}>
            <div className={styles.statLabel}>{label}</div>
            <div className={`${styles.statValue} ${styles[status]}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* Feature grid */}
      <div className={styles.cards}>
        {FEATURES.map(({ href, icon, title, desc }) => (
          <Link key={href} href={href} className={styles.card}>
            <span className={styles.cardIcon}>{icon}</span>
            <div className={styles.cardTitle}>{title}</div>
            <p className={styles.cardDesc}>{desc}</p>
          </Link>
        ))}
      </div>

      <p className={styles.notice}>
        Previous Streamlit UI available at{" "}
        <a href="http://localhost:8090" target="_blank" rel="noopener noreferrer">localhost:8090</a>.
      </p>
    </div>
  );
}
