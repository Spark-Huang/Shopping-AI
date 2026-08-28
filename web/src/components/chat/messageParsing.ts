import { marked } from "marked";

export const createMarkdownConverter = (
  role: string
): { makeHtml: (source: string) => string } => {
  const classMap: Record<string, string> = {
    h1: `messages__item--${role}--h1`,
    h2: `messages__item--${role}--h2`,
    ul: `messages__item--${role}--ul`,
    li: `messages__item--${role}--li`,
    ol: `messages__item--${role}--ol`,
    p: `messages__item--${role}--p`,
  };

  return {
    makeHtml: (source: string): string => {
      marked.setOptions({ async: false, breaks: true, gfm: true });
      const html = marked.parse(source) as string;
      let output = html;
      for (const key of Object.keys(classMap)) {
        output = output.replace(
          new RegExp(`<${key}(\\s|>)`, "g"),
          `<${key} class="${classMap[key]}"$1`
        );
      }
      return output;
    },
  };
};

export const preprocessAssistantContent = (content: string): string =>
  content
    .replace(/^\* /gm, "• ")
    .replace(/^- /gm, "• ")
    .replace(/^\d+\. /gm, (match) => match);
