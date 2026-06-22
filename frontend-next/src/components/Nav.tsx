"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Nav.module.css";

const LINKS = [
  { href: "/explore",       label: "Explore" },
  { href: "/morning-paper", label: "Morning paper" },
  { href: "/chat",          label: "Ask AI" },
];

export default function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [showPlatforms, setShowPlatforms] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close menu on route change
  useEffect(() => { setOpen(false); }, [pathname]);

  // Lock scroll when menu is open
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowPlatforms(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <>
      <header className={styles.header}>
        <div className={styles.inner}>
          {/* Brand & Platform */}
          <div className={styles.brandGroup}>
            <Link href="/" className={styles.brand}>
              <span className={styles.brandDot} aria-hidden />
              Cloud News
            </Link>
            <div className={styles.platformDropdown} ref={dropdownRef}>
              <button 
                className={styles.platformTrigger} 
                onClick={() => setShowPlatforms(!showPlatforms)}
                aria-expanded={showPlatforms}
                aria-label="Select Cloud Platform"
              >
                Google Cloud <span className={styles.arrow}>▾</span>
              </button>
              {showPlatforms && (
                <div className={styles.dropdownMenu}>
                  <div className={`${styles.dropdownItem} ${styles.activeItem}`}>
                    <span className={`${styles.dot} ${styles.gcpDot}`}></span>
                    Google Cloud (GCP)
                  </div>
                  <div className={`${styles.dropdownItem} ${styles.disabledItem}`}>
                    <span className={`${styles.dot} ${styles.awsDot}`}></span>
                    AWS (Upcoming)
                  </div>
                  <div className={`${styles.dropdownItem} ${styles.disabledItem}`}>
                    <span className={`${styles.dot} ${styles.azureDot}`}></span>
                    Microsoft Azure (Upcoming)
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Desktop links */}
          <nav className={styles.desktopNav} aria-label="Main">
            {LINKS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={`${styles.navLink} ${pathname.startsWith(href) ? styles.active : ""}`}
              >
                {label}
              </Link>
            ))}
          </nav>

          {/* Hamburger */}
          <button
            className={styles.burger}
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={open ? "Close menu" : "Open menu"}
          >
            <span className={`${styles.burgerBar} ${open ? styles.burgerTop : ""}`} />
            <span className={`${styles.burgerBar} ${open ? styles.burgerMid : ""}`} />
            <span className={`${styles.burgerBar} ${open ? styles.burgerBot : ""}`} />
          </button>
        </div>
      </header>

      {/* Mobile drawer */}
      {open && (
        <div className={styles.drawer} onClick={() => setOpen(false)}>
          <nav className={styles.drawerNav} onClick={(e) => e.stopPropagation()} aria-label="Mobile">
            {LINKS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={`${styles.drawerLink} ${pathname.startsWith(href) ? styles.drawerActive : ""}`}
              >
                {label}
              </Link>
            ))}
            <a
              href="http://localhost:8090"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.drawerLegacy}
            >
              Legacy Streamlit UI ↗
            </a>
          </nav>
        </div>
      )}
    </>
  );
}
