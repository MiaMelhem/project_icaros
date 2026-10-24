"use client";

import ThemeToggle from "./ThemeToggle";

export default function AppHeader() {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <div className="app-brand">
          <div className="app-logo" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="14" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
              <circle cx="16" cy="16" r="9" fill="currentColor" opacity="0.15" />
              <circle cx="22" cy="10" r="3" fill="currentColor" />
            </svg>
          </div>
          <div>
            <h1 className="app-title">ICAROS</h1>
            <p className="app-tagline">
              Intelligent Crater-Aware Route Optimization
            </p>
          </div>
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}
