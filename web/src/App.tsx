/**
 * Main application shell
 * Symy-style mobile-first shell with bottom tab navigation:
 * status bar / [Messages | Cart | Me] panels / bottom tab bar.
 *
 * Tab switching keeps ALL three panels mounted and toggles visibility via
 * the [hidden] attribute (display:none):
 *  - unmounting the chatbox would abort in-flight SSE streams,
 *  - unmounting the cart would lose its loaded state.
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { useTranslation } from "react-i18next";

import Navbar from "./components/Navbar";
import AuthPage from "./components/auth/AuthPage";
import Chatbox from "./components/chat/ChatWindow";
import CartPanel from "./components/cart/CartPanel";
import GuizhouPage from "./components/guizhou/GuizhouPage";
import MePage from "./components/me/MePage";
import BottomTabBar, { type TabId } from "./components/BottomTabBar";
import Footer from "./components/Footer";
import { AuthUser, clearAuth, getAuthUser } from "./lib/auth";
import { setAppLanguage, type AppLang } from "./i18n";
import {
  SAFETY_STORAGE_KEY,
  readSafetyState,
  writeSafetyState,
} from "./safetyToggle";
import {
  DIALECT_STORAGE_KEY,
  readDialectState,
  writeDialectState,
} from "./dialectToggle";

const App: React.FC = () => {
  const [user, setUser] = useState<AuthUser | null>(getAuthUser);
  const [activeTab, setActiveTab] = useState<TabId>("messages");
  const [safetyEnabled, setSafetyEnabled] =
    useState(readSafetyState);
  useEffect(() => {
    const syncState = (event: StorageEvent) => {
      if (event.key === SAFETY_STORAGE_KEY) {
        setSafetyEnabled(event.newValue !== "false");
      }
    };
    window.addEventListener("storage", syncState);
    return () => window.removeEventListener("storage", syncState);
  }, []);
  const changeSafety = useCallback((enabled: boolean) => {
    setSafetyEnabled(enabled);
    writeSafetyState(enabled);
  }, []);
  // Guizhou-dialect reply mode: off by default, persisted like safety.
  const [dialectEnabled, setDialectEnabled] =
    useState(readDialectState);
  useEffect(() => {
    const syncState = (event: StorageEvent) => {
      if (event.key === DIALECT_STORAGE_KEY) {
        setDialectEnabled(event.newValue === "true");
      }
    };
    window.addEventListener("storage", syncState);
    return () => window.removeEventListener("storage", syncState);
  }, []);
  const changeDialect = useCallback((enabled: boolean) => {
    setDialectEnabled(enabled);
    writeDialectState(enabled);
  }, []);
  // Bumped whenever a cart add/remove is detected in an assistant reply;
  // CartPanel refetches the cart when this changes.
  const [cartRefreshSignal, setCartRefreshSignal] = useState<number>(0);
  const handleCartChange = useCallback(() => {
    setCartRefreshSignal((n) => n + 1);
  }, []);
  const handleOrderChange = useCallback(() => setCartRefreshSignal((n) => n + 1), []);
  // Total item count reported by CartPanel; drives the Cart tab badge.
  const [cartCount, setCartCount] = useState<number>(0);
  const handleCartCountChange = useCallback((count: number) => {
    setCartCount(count);
  }, []);
  const addFavoriteToCartRef = useRef<((productName: string) => void) | null>(null);
  const handleFavoriteAddToCart = useCallback((productName: string) => {
    setActiveTab("messages");
    addFavoriteToCartRef.current?.(productName);
  }, []);
  // Product-discovery handoff: the catalog can send a grounded shopping
  // prompt to the agent and jump back to the conversation.
  const tourQueryRef = useRef<((query: string) => void) | null>(null);
  const handleTourStart = useCallback((query: string) => {
    setActiveTab("messages");
    tourQueryRef.current?.(query);
  }, []);
  // New-chat handoff: the Navbar "more choices" menu asks the chatbox for
  // an explicit fresh start (drops the persistent user id + welcome flow).
  const requestNewChatRef = useRef<(() => void) | null>(null);
  const handleNewChat = useCallback(() => {
    setActiveTab("messages");
    requestNewChatRef.current?.();
  }, []);
  // Language toggle for the Navbar menu (same behaviour as the Me tab).
  const { i18n } = useTranslation();
  const handleToggleLanguage = useCallback(() => {
    const next: AppLang = i18n.language?.startsWith("zh") ? "en" : "zh";
    setAppLanguage(next);
  }, [i18n.language]);
  const handleLogout = useCallback(() => {
    clearAuth();
    setUser(null);
    setActiveTab("messages");
  }, []);

  if (!user) {
    return <AuthPage onAuthenticated={setUser} />;
  }

  return (
    <div className="app-shell">
      <div className="phone-container">
        <Navbar
          onNavigate={setActiveTab}
          onNewChat={handleNewChat}
          onToggleLanguage={handleToggleLanguage}
        />
        <main className="tab-panels">
          {/* Panels stay mounted forever; only display toggles. */}
          <section
            className="tab-panel"
            hidden={activeTab !== "messages"}
            data-testid="panel-messages"
          >
            <Chatbox
              requestCommandRef={addFavoriteToCartRef}
              requestTourRef={tourQueryRef}
              requestNewChatRef={requestNewChatRef}
              onCartChange={handleCartChange}
              visible={activeTab === "messages"}
              safetyEnabled={safetyEnabled}
              onSafetyChange={changeSafety}
              dialectEnabled={dialectEnabled}
            />
          </section>
          <section
            className="tab-panel"
            hidden={activeTab !== "discover"}
            data-testid="panel-discover"
          >
            <GuizhouPage
              onCartChange={handleCartChange}
              onTourStart={handleTourStart}
            />
          </section>
          <section
            className="tab-panel"
            hidden={activeTab !== "cart"}
            data-testid="panel-cart"
          >
            {/* Cart lives inside the phone container as a full-page tab view
                while keeping full cart interactivity. */}
            <CartPanel
              refreshSignal={cartRefreshSignal}
              onCountChange={handleCartCountChange}
              onOrderChange={handleOrderChange}
            />
          </section>
          <section
            className="tab-panel"
            hidden={activeTab !== "me"}
            data-testid="panel-me"
          >
            <MePage
              onAddToCart={handleFavoriteAddToCart}
              onOrderChange={handleOrderChange}
              safetyEnabled={safetyEnabled}
              onSafetyChange={changeSafety}
              dialectEnabled={dialectEnabled}
              onDialectChange={changeDialect}
              onLogout={handleLogout}
            />
          </section>
        </main>
        <Footer />
        <BottomTabBar
          activeTab={activeTab}
          onChange={setActiveTab}
          cartCount={cartCount}
        />
      </div>
      <ToastContainer position="top-center" autoClose={1500} />
    </div>
  );
};

export default App;
