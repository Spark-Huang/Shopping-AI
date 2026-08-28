export const SAFETY_STORAGE_KEY = "safety-enabled";

const parseStoredState = (value: string | null): boolean => value !== "false";

export const readSafetyState = (): boolean => {
  try {
    return parseStoredState(
      window.localStorage.getItem(SAFETY_STORAGE_KEY)
    );
  } catch {
    return true;
  }
};

export const writeSafetyState = (enabled: boolean): void => {
  try {
    window.localStorage.setItem(
      SAFETY_STORAGE_KEY,
      enabled ? "true" : "false"
    );
  } catch {
    /* Keep the in-memory state when storage is unavailable. */
  }
};
