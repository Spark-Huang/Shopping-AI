const FIXED_USER_ID = 1;

export const getOrCreateUserId = (): number => {
  const storedId = localStorage.getItem("shopping_user_id");
  const legacySessionId = sessionStorage.getItem("shopping_user_id");

  if (storedId !== String(FIXED_USER_ID) || legacySessionId !== null) {
    localStorage.setItem("shopping_user_id", String(FIXED_USER_ID));
    sessionStorage.removeItem("shopping_user_id");
  }
  return FIXED_USER_ID;
};

export const clearUserIdentity = (): void => {
  localStorage.setItem("shopping_user_id", String(FIXED_USER_ID));
  sessionStorage.removeItem("shopping_user_id");
};
