import { config } from "../../config/appConfig";
import { authFetch } from "../../lib/auth";
import type React from "react";
import { showCartNotification } from "../../lib/cartEvents";
import { parseImagesPayload, ProductPayload } from "../../lib/images";
import type { ChatMessage } from "./ChatWindow.types";

export interface StreamCallbacks {
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  setLastAssistantIndex: (index: number) => void;
  setIsSlow: (stage: "first" | "second" | "third" | false) => void;
  onCartChange?: () => void;
  onContent?: () => void;
}

export const updateAssistantMessage = (
  messages: ChatMessage[],
  content: string,
  setLastAssistantIndex: (index: number) => void
): ChatMessage[] => {
  const updated = [...messages];
  const last = updated[updated.length - 1];

  if (last?.role === "assistant") {
    updated[updated.length - 1] = { ...last, content };
  } else {
    updated.push({
      role: "assistant",
      content,
      productName: "",
    });
    setLastAssistantIndex(updated.length - 1);
  }

  return updated;
};

export const replaceLastMessageWithImages = (
  messages: ChatMessage[],
  payload: ProductPayload
): ChatMessage[] => {
  const images = parseImagesPayload(payload);
  const updated = [...messages];
  updated[updated.length - 1] = {
    ...updated[updated.length - 1],
    role: "image_row",
    content: images,
  };
  return updated;
};

export const readChatStream = async (
  payload: unknown,
  fullResponse: string,
  shownCartOperations: Set<string>,
  toast: any,
  streamInterruptedMessage: string,
  callbacks: StreamCallbacks
): Promise<string> => {
  const url = `${config.api.baseUrl}${config.api.endpoints.stream}`;
  const response = await authFetch(url, {
    method: "POST",
    mode: "cors",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let responseText = fullResponse;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split("\n").filter((line) => line.startsWith("data:"));

    for (const line of lines) {
      const raw = line.replace(/^data:\s*/, "");
      if (raw === "[DONE]") return responseText;

      try {
        const event = JSON.parse(raw);
        const { type, payload: eventPayload } = event;

        if (type === "error") {
          responseText +=
            typeof eventPayload === "string"
              ? eventPayload
              : streamInterruptedMessage;
          callbacks.setMessages((messages) =>
            updateAssistantMessage(
              messages,
              responseText,
              callbacks.setLastAssistantIndex
            )
          );
          continue;
        }

        if (type === "content") {
          responseText += eventPayload;
          callbacks.setIsSlow(false);
          showCartNotification(
            responseText,
            shownCartOperations,
            toast,
            callbacks.onCartChange
          );
          callbacks.onContent?.();
        } else if (type === "images") {
          callbacks.setMessages((messages) =>
            replaceLastMessageWithImages(messages, eventPayload)
          );
        }

        callbacks.setMessages((messages) =>
          updateAssistantMessage(
            messages,
            responseText,
            callbacks.setLastAssistantIndex
          )
        );
      } catch {
        continue;
      }
    }
  }

  return responseText;
};
