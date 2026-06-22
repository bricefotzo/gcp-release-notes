"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHealth, getFilterOptions, type FilterOptions } from "@/lib/api";
import styles from "./page.module.css";

type Status = "loading" | "ok" | "error";

const FEATURES = [
  { href: "/explore",       icon: "↓", title: "Explore",       desc: "Search and filter release notes across every GCP product and note type." },
  { href: "/morning-paper", icon: "☀", title: "Morning paper", desc: "A daily briefing on what changed in your stack — readable in 2 minutes." },
  { href: "/chat",          icon: "◌", title: "Ask AI",        desc: "Chat with the release notes. Ask anything, get grounded answers." },
  { href: "/share",         icon: "↗", title: "Share",         desc: "One click to generate a LinkedIn or X post and open the app to post it." },
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
