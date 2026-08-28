/**
 * Footer component — slim tab-bar style strip.
 *
 * The three policy links (Contact Us / Guidelines & FAQ / Privacy Policy)
 * are intentionally hidden until real pages exist: dead spans that look
 * clickable are worse than no links (PM review item 6 / marketing B4).
 * When the pages land, restore the markup below inside .footer-strip:
 *
 *   <span>{t("footer.contactUs")}</span>
 *   <span>{t("footer.guidelines")}</span>
 *   <span>{t("footer.privacyPolicy")}</span>
 *
 * The i18n keys (footer.*) are kept in en.json/zh.json for that day.
 */

import React from "react";

const Footer: React.FC = () => {
  // Policy links hidden until real pages exist (see comment above).
  return null;
};

export default Footer;
