/**
 * Navbar component — Symy style: brand status bar.
 *
 * Slimmed down for the bottom-tab layout: the language switcher moved
 * to the "Me" tab, so the status bar only keeps the brand word.
 */

import React from "react";
import MenuIcon from "@mui/icons-material/Menu";

/**
 * Navbar component — Symy style: brand status bar.
 *
 * Slimmed down for the bottom-tab layout: the language switcher moved
 * to the "Me" tab, so the status bar only keeps the brand word.
 * Category chips removed (r16-batch2 D1).
 */

const Navbar: React.FC = () => {
  return (
    <div>
      {/* Top status bar: brand only (language switcher now lives in the Me tab) */}
      <div className="status-bar">
        <div className="status-bar__brand">
          <MenuIcon sx={{ color: "var(--text-secondary)" }} fontSize="small" />
          <span className="status-bar__brand-dot" aria-hidden="true" />
          Guikela
        </div>
      </div>
    </div>
  );
};

export default Navbar;
