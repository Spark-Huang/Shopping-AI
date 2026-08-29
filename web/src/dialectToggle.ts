export const DIALECT_STORAGE_KEY = "dialect-enabled";

const parseStoredState = (value: string | null): boolean => value === "true";

export const readDialectState = (): boolean => {
  try {
    return parseStoredState(
      window.localStorage.getItem(DIALECT_STORAGE_KEY)
    );
  } catch {
    // Off by default when storage is unavailable.
    return false;
  }
};

export const writeDialectState = (enabled: boolean): void => {
  try {
    window.localStorage.setItem(
      DIALECT_STORAGE_KEY,
      enabled ? "true" : "false"
    );
  } catch {
    /* Keep the in-memory state when storage is unavailable. */
  }
};
