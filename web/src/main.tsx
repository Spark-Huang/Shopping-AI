/**
 * Main entry point for the web application
 */

import React from "react";
import ReactDOM from "react-dom/client";
import "./styles/global.css";
import "./styles/chat.css";
import "./i18n";
import App from "./App";
import { config } from "./config/appConfig";

const root = ReactDOM.createRoot(document.getElementById("root") as HTMLElement);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

for (const selector of [
  'meta[property="og:image"]',
  'meta[name="twitter:image"]',
]) {
  document
    .querySelector(selector)
    ?.setAttribute("content", "/og-image.jpg");
}
