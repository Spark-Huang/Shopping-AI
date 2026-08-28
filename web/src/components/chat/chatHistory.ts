export const HISTORY_SUMMARY_LENGTH = 80;
export const HISTORY_INTERNAL_PATTERN =
  /PRICE:|Agent Response:|User asked:|CSV:|These products are available in the catalog:|\s\|\s/i;

export const splitHistoryIntoBubbles = (context: string): string[] => {
  return context
    .split(/\n\s*\n/)
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0)
    .flatMap((segment) => {
      const readableLines = segment
        .split(/\n+/)
        .filter((line) => !HISTORY_INTERNAL_PATTERN.test(line));
      const readable = readableLines.join(" ").replace(/\s+/g, " ").trim();
      if (!readable) return [];
      return readable.length > HISTORY_SUMMARY_LENGTH
        ? `${readable.slice(0, HISTORY_SUMMARY_LENGTH).trimEnd()}…`
        : readable;
    });
};
