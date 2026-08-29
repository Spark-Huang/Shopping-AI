export type MessageRole =
  | "user"
  | "assistant"
  | "system"
  | "image"
  | "image_row"
  | "user_image";

export interface ImageContent {
  productUrl: string;
  productName: string;
  externalUrl?: string;
  price?: number;
  currency?: string;
  rating?: number;
}

export interface ImageRowContent extends Array<ImageContent> {}

export interface MessageData {
  role: MessageRole;
  content: string | ImageContent | ImageRowContent;
  productName: string;
  isHistory?: boolean;
}

export interface ChatboxProps {
  requestCommandRef?: React.MutableRefObject<
    ((command: string) => void) | null
  >;
  /** Ref the shell calls to send a culture-tour query into the chat. */
  requestTourRef?: React.MutableRefObject<
    ((query: string) => void) | null
  >;
  /** Ref the shell calls to start a fresh conversation (Navbar menu). */
  requestNewChatRef?: React.MutableRefObject<(() => void) | null>;
  onCartChange?: () => void;
  visible?: boolean;
  safetyEnabled: boolean;
  onSafetyChange: (enabled: boolean) => void;
  /** Guizhou-dialect reply mode, toggled from the Me page. */
  dialectEnabled?: boolean;
}

export interface SafeHTMLProps {
  html: string;
}

export interface ChatMessageProps {
  role: MessageRole;
  content: string | ImageContent | ImageRowContent;
  productName: string;
  isWelcome?: boolean;
  exampleQuestions?: string[];
  onExampleClick?: (question: string) => void;
  onAddToCart?: (product: ImageContent | string) => void;
  cartAddInFlight?: boolean;
  onToggleFavorite?: (product: ImageContent) => void;
  /** Forwarded to the product detail modal so cart adds update the badge. */
  onCartChange?: () => void;
  isFavorite?: boolean;
  isHistory?: boolean;
}

export interface ProductInfo {
  image?: string;
  url?: string;
  price?: number;
  currency?: string;
  rating?: number;
}
