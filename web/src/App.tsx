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

import Navbar from "./components/Navbar";
import AuthPage from "./components/auth/AuthPage";
import Chatbox from "./components/chat/ChatWindow";
import CartPanel from "./components/cart/CartPanel";
import MePage from "./components/me/MePage";
import BottomTabBar, { type TabId } from "./components/BottomTabBar";
import Footer from "./components/Footer";
import { AuthUser, clearAuth, getAuthUser } from "./lib/auth";
import {
  SAFETY_STORAGE_KEY,
  readSafetyState,
  writeSafetyState,
} from "./safetyToggle";

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
        <Navbar />
        <main className="tab-panels">
          {/* Panels stay mounted forever; only display toggles. */}
          <section
            className="tab-panel"
            hidden={activeTab !== "messages"}
            data-testid="panel-messages"
          >
            <Chatbox
              requestCommandRef={addFavoriteToCartRef}
              onCartChange={handleCartChange}
              visible={activeTab === "messages"}
              safetyEnabled={safetyEnabled}
              onSafetyChange={changeSafety}
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
      <ToastContainer position="top-center" />
    </div>
  );
};

export default App;
