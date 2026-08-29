import i18n from "../i18n";

export interface CartOperation {
  type: "add" | "remove";
  item: string;
}

const cleanItemName = (item: string): string => {
  return item.replace(/\*\*/g, "").trim();
};

const isSecondPersonCartNarration = (message: string): boolean => {
  const lower = message.toLowerCase();
  return (
    /\byou(?:'ve| have)?\s+added\b/.test(lower) ||
    /\byou\s+added\b/.test(lower) ||
    /\byou(?:'ve| have)?\s+removed\b/.test(lower) ||
    /\byou\s+removed\b/.test(lower)
  );
};

export const detectCartOperation = (
  message: string
): CartOperation | null => {
  if (isSecondPersonCartNarration(message)) return null;

  const addPattern =
    /(?:added.*?(?:of\s+)?['"]?([^'"]+?)['"]?\s+to.*cart|added.*?\*\*([^*]+)\*\*.*to.*cart)/i;
  const removePattern =
    /(?:removed.*?(?:of\s+)?['"]?([^'"]+?)['"]?\s+from.*cart|removed.*?\*\*([^*]+)\*\*.*from.*cart)/i;

  let match = message.match(addPattern);
  if (match) {
    const item = match[1] || match[2];
    if (item) return { type: "add", item: cleanItemName(item) };
  }

  match = message.match(removePattern);
  if (match) {
    const item = match[1] || match[2];
    if (item) return { type: "remove", item: cleanItemName(item) };
  }

  return null;
};

export const showCartNotification = (
  fullResponse: string,
  shownOperations: Set<string>,
  toast: any,
  onCartChange?: () => void
): void => {
  const cartOperation = detectCartOperation(fullResponse);
  if (!cartOperation) return;

  const operationKey = `${cartOperation.type}-${cartOperation.item}`;
  if (shownOperations.has(operationKey)) return;

  shownOperations.add(operationKey);
  onCartChange?.();

  if (cartOperation.type === "add") {
    toast.success(i18n.t("cart.added"), { autoClose: 1500, className: "toast-pill" });
    return;
  }
  toast.info(i18n.t("cart.removed", { item: cartOperation.item }));
};
