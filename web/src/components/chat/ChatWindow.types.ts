import type { ImageContent, MessageRole } from "../../types/chat";

export interface ChatMessage {
  role: MessageRole;
  content: any;
  productName: string;
  isWelcome?: boolean;
  isHistory?: boolean;
  exampleQuestions?: string[];
}

export type ChatImageState = {
  image: string;
  previewImage: string;
};

export interface SessionSummary {
  id: number;
  title: string;
}
