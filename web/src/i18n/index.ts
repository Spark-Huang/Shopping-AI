/**
 * i18n setup: react-i18next with en/zh resources.
 * Default language follows the browser (navigator.language),
 * manual choice persists in localStorage("i18n-lang").
 */

import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./en.json";
import zh from "./zh.json";

export const LANG_STORAGE_KEY = "i18n-lang";
export const SUPPORTED_LANGS = ["en", "zh"] as const;
export type AppLang = (typeof SUPPORTED_LANGS)[number];

/** Detect initial language: localStorage choice > browser language > en */
export const detectInitialLang = (): AppLang => {
  try {
    const stored = window.localStorage.getItem(LANG_STORAGE_KEY);
    if (stored && (SUPPORTED_LANGS as readonly string[]).includes(stored)) {
      return stored as AppLang;
    }
  } catch {
    /* localStorage unavailable — fall through to browser detection */
  }
  const nav = window.navigator.language?.toLowerCase() ?? "en";
  return nav.startsWith("zh") ? "zh" : "en";
};

/** Persist language choice and keep <html lang> in sync */
export const setAppLanguage = (lang: AppLang): void => {
  i18n.changeLanguage(lang);
  try {
    window.localStorage.setItem(LANG_STORAGE_KEY, lang);
  } catch {
    /* ignore persistence failures */
  }
  document.documentElement.lang = lang;
};

const initialLang = detectInitialLang();

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    zh: { translation: zh },
  },
  lng: initialLang,
  fallbackLng: "en",
  interpolation: { escapeValue: false }, // React already escapes
});

// Keep <html lang> and <title> in sync from the start and on any later change
document.documentElement.lang = initialLang;
document.title = initialLang === "zh" ? zh.documentTitle : en.documentTitle;
i18n.on("languageChanged", (lng: string) => {
  document.documentElement.lang = lng;
  document.title = lng === "zh" ? zh.documentTitle : en.documentTitle;
});

export default i18n;
