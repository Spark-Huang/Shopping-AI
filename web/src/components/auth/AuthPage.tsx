/**
 * AuthPage: full-screen sign-in / registration gate shown by App when there
 * is no authenticated session. On success it stores the token via lib/auth
 * and reports the user upward so the app shell can mount.
 */

import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { AuthUser, AuthError, loginUser, registerUser } from "../../lib/auth";
import "./auth.css";

type AuthMode = "login" | "register";

type AuthPageProps = {
  onAuthenticated: (user: AuthUser) => void;
};

const AuthPage: React.FC<AuthPageProps> = ({ onAuthenticated }) => {
  const { t } = useTranslation();
  const [mode, setMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user =
        mode === "login"
          ? await loginUser(username.trim(), password)
          : await registerUser(username.trim(), password);
      onAuthenticated(user);
    } catch (err) {
      const message =
        err instanceof AuthError && err.message
          ? err.message
          : mode === "login"
            ? t("auth.loginFailed")
            : t("auth.registerFailed");
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    setMode((current) => (current === "login" ? "register" : "login"));
    setError("");
  };

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <h1 className="auth-card__title">{t("auth.title")}</h1>
        <p className="auth-card__subtitle">{t("auth.subtitle")}</p>

        <label className="auth-field">
          <span>{t("auth.usernameLabel")}</span>
          <input
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
            minLength={3}
          />
        </label>

        <label className="auth-field">
          <span>{t("auth.passwordLabel")}</span>
          <input
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={6}
          />
        </label>

        {error && <p className="auth-card__error">{error}</p>}

        <button className="auth-card__submit" type="submit" disabled={loading}>
          {mode === "login" ? t("auth.loginButton") : t("auth.registerButton")}
        </button>

        <button
          className="auth-card__switch"
          type="button"
          onClick={toggleMode}
        >
          {mode === "login"
            ? t("auth.switchToRegister")
            : t("auth.switchToLogin")}
        </button>
      </form>
    </div>
  );
};

export default AuthPage;