import React, { useState, useEffect, useRef } from "react";
import { toast } from "react-toastify";
import SendIcon from "@mui/icons-material/Send";
import CancelIcon from "@mui/icons-material/Cancel";
import UploadIcon from "@mui/icons-material/Upload";
import FormGroup from "@mui/material/FormGroup";
import FormControlLabel from "@mui/material/FormControlLabel";
import Switch from "@mui/material/Switch";
import { styled } from "@mui/material/styles";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faTimesCircle } from "@fortawesome/free-solid-svg-icons";

import MessageItem from "./MessageItem";
import { ChatboxProps } from "../../types/chat";
import {
  clearUserIdentity,
  getOrCreateUserId,
} from "../../lib/identity";
import { readFavorites, toggleFavorite } from "../../lib/favorites";
import type { ImageContent } from "../../types/chat";
import { addContext, fetchHistory } from "../../api/historyApi";
import { addCartProduct } from "../../api/cartApi";
import { useTranslation } from "react-i18next";
import {
  convertToBase64,
  createImagePreview,
  validateImageFile,
} from "./chatInput";
import {
  hasMonthlyBudgetLine,
  splitHistoryIntoBubbles,
} from "./chatHistory";
import { readChatStream } from "./ChatWindow.useStream";
import { scheduleSession, sleep } from "./streamSession";
import type { ChatMessage } from "./ChatWindow.types";

/**
 * Main chatbox component for Shopping AI.
 */

/** How close (px) to the bottom counts as "pinned", for auto-follow scrolling. */
const NEAR_BOTTOM_PX = 80;

const RESET_CONFIRM_TIMEOUT_MS = 3000;

// Symy brand blue switch
const CustomSwitch = styled(Switch)(({ theme }) => ({
  "& .MuiSwitch-switchBase.Mui-checked": {
    color: "#1d4ed8",
  },
  "& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track": {
    backgroundColor: "rgba(29, 78, 216, 0.45)",
  },
  "& .MuiSwitch-switchBase": {
    color: "#9ca3af",
  },
  "& .MuiSwitch-track": {
    backgroundColor: "var(--glass-border, rgba(0,0,0,0.10))",
  },
}));

const Chatbox: React.FC<ChatboxProps> = ({
  requestCommandRef,
  onCartChange,
  visible = true,
  safetyEnabled,
  onSafetyChange,
}) => {
  const { t, i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [hasBeenOpened, setHasBeenOpened] = useState<boolean>(false);
  const [newMessage, setNewMessage] = useState<string>("");
  const [image, setImage] = useState("");
  const [previewImage, setPreviewImage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [favorites, setFavorites] = useState(() => readFavorites());
  const [isLoading, setIsLoading] = useState(false);
  // True once a send is taking unusually long (see SLOW_HINT_DELAY_MS);
  // drives the "still searching..." hint under the loader bubble.
  const [isSlow, setIsSlow] = useState<"first" | "second" | "third" | false>(
    false
  );
  const [isResetArmed, setIsResetArmed] = useState(false);
  const [cartAddInFlight, setCartAddInFlight] = useState(false);
  const messageRefs = useRef<React.RefObject<HTMLDivElement>[]>([]);
  const [lastAssistantIndex, setLastAssistantIndex] = useState<number | null>(
    null
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const shownCartOperations = useRef<Set<string>>(new Set());
  // Scroll-position preservation across tab switches: display:none resets
  // scrollTop, so we mirror the live offset into savedScrollTopRef and put it
  // back once the Messages tab becomes visible again.
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const savedScrollTopRef = useRef<number>(0);
  // Mirrors of the previous render's values, used to detect "tab became
  // visible" and "message count grew" inside the scroll-management effect.
  const prevCountRef = useRef<number>(0);
  const prevVisibleRef = useRef<boolean>(true);
  const resetConfirmTimeoutRef = useRef<number | null>(null);
  const sendInFlightRef = useRef(false);

  const disarmResetConfirmation = () => {
    if (resetConfirmTimeoutRef.current !== null) {
      window.clearTimeout(resetConfirmTimeoutRef.current);
      resetConfirmTimeoutRef.current = null;
    }
    setIsResetArmed(false);
  };

  // Event handlers
  const toggleSafety = () => {
    const nextState = !safetyEnabled;
    onSafetyChange(nextState);
    toast.info(
      t(nextState ? "chatbox.safetyOnToast" : "chatbox.safetyOffToast")
    );
  };

  const handleNewMessageChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setNewMessage(event.target.value);
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];

    const validationError = validateImageFile(file, t);
    if (validationError) {
      toast.error(validationError);
      return;
    }

    try {
      const base64Image = await convertToBase64(file);
      setImage(base64Image);

      setPreviewImage(createImagePreview(base64Image));

      e.target.value = "";
    } catch (error) {
      toast.error(t("errors.failedToUpload"));
    }
  };

  const clearImage = () => {
    setPreviewImage("");
    setImage("");
  };

  const addMessage = (
    role: ChatMessage["role"],
    content: any,
    productName: string = "",
    isWelcome: boolean = false,
    isHistory: boolean = false,
    showOnboardingActions: boolean = false
  ) => {
    setMessages((prevMessages) => {
      const newMessages = [
        ...prevMessages,
        {
          role,
          content,
          productName,
          isWelcome,
          isHistory,
          showOnboardingActions,
        },
      ];
      messageRefs.current = newMessages.map(
        (_, i) => messageRefs.current[i] || React.createRef<HTMLDivElement>()
      );

      if (
        role === "assistant" &&
        (lastAssistantIndex === null ||
          lastAssistantIndex < prevMessages.length)
      ) {
        setLastAssistantIndex(prevMessages.length);
      }

      return newMessages;
    });
  };

  const updateLastMessage = (
    newContent: any,
    role?: ChatMessage["role"],
    appendContent?: boolean
  ) => {
    setMessages((prevMessages) => {
      if (prevMessages.length === 0) return prevMessages;

      const updatedMessages = [...prevMessages];
      const lastMessageIndex = updatedMessages.length - 1;

      if (role) {
        updatedMessages[lastMessageIndex].role = role;
      }

      if (typeof newContent === "string") {
        updatedMessages[lastMessageIndex] = {
          ...updatedMessages[lastMessageIndex],
          content: appendContent
            ? newContent
            : updatedMessages[lastMessageIndex].content + newContent,
        };
      } else {
        updatedMessages[lastMessageIndex] = {
          ...updatedMessages[lastMessageIndex],
          content: newContent,
        };
      }

      return updatedMessages;
    });
  };

  const handleSendMessage = async (overrideMessage?: string) => {
    const outgoing = (overrideMessage ?? newMessage).trim();
    if (!outgoing && !image) return;
    if (sendInFlightRef.current) return;
    sendInFlightRef.current = true;

    // Clear previous cart operation notifications for new message
    shownCartOperations.current.clear();

    const userId = getOrCreateUserId();
    setIsLoading(true);
    setIsSlow(false);

    const session = scheduleSession(setIsLoading, setIsSlow, () => {
      sendInFlightRef.current = false;
    });

    try {
      // Add user message
      if (outgoing) {
        addMessage("user", outgoing, "");
      }
      if (image) {
        addMessage("user_image", previewImage, "");
      }

      // Add loading message
      addMessage("assistant", "loader", "");
      setNewMessage("");

      // Prepare API request
      // `language` (D5): active i18n language so the chatter replies in
      // the language the user is reading.
      const payload = {
        user_id: userId,
        query: outgoing,
        safety: safetyEnabled,
        image: image || "",
        image_bool: !!image,
        language: i18n.language?.startsWith("zh") ? "zh" : "en",
      };

      // Clear image immediately after preparing payload
      setImage("");
      setPreviewImage("");

      const fullResponse = await readChatStream(payload, "", shownCartOperations.current, toast, t("errors.streamInterrupted"), {
        setMessages,
        setLastAssistantIndex,
        setIsSlow,
        onCartChange,
        onContent: session.onContent,
      });

      // Stream ended without [DONE]: if nothing was rendered, treat it as
      // an interrupted stream (the loader bubble must not sit forever).
      if (!fullResponse) {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last?.role === "assistant" && last.content === "loader") {
            updated[updated.length - 1] = {
              ...last,
              content: t("errors.streamInterrupted"),
            };
          }
          return updated;
        });
      }
    } catch (error) {
      console.error("Error sending message:", error);

      // Replace the loader bubble with an in-conversation error bubble so
      // the failed attempt is visible and self-explaining (PM review
      // item 2), plus the transient toast for immediate feedback.
      toast.error(t("errors.failedToSend"));
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.role === "assistant" && last.content === "loader") {
          updated[updated.length - 1] = {
            ...last,
            content: t("errors.streamInterrupted"),
          };
        }
        return updated;
      });
    } finally {
      session.finish();
    }
  };

  const handleKeyUp = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && !isLoading) {
      handleSendMessage();
    }
  };

  /**
   * Reset/replay entry point.
   *
   * Two call sites, two behaviours:
   *  - mount (userInitiated=false): session replay (D3). If the server has a
   *    conversation context for the stored user id, replay it as
   *    History-badged bubbles and KEEP the id so follow-up messages continue
   *    the same server-side context. Empty/failed lookup falls through to
   *    the welcome flow.
   *  - Reset button (userInitiated=true): explicit fresh start — drop the
   *    persistent user id (next message mints a new user) and show the welcome.
   */
  const handleReset = async (userInitiated: boolean = false) => {
    if (!userInitiated) {
      try {
        const history = await fetchHistory(getOrCreateUserId());
        const bubbles = splitHistoryIntoBubbles(history.context || "");
        if (bubbles.length > 0) {
          for (const bubble of bubbles) {
            addMessage("assistant", bubble, "", false, true);
          }
          return;
        }
      } catch (e) {
        // Network/API failure or first-time user: fall through to welcome.
        console.warn("Chatbox: history replay skipped", e);
      }
    }

    setMessages([]);
    setImage("");
    setPreviewImage("");
    if (userInitiated) {
      clearUserIdentity();
    }

    await sleep(1000);
    addMessage("assistant", "", "", true, false, true);

    await sleep(1000);
    const introduction = t("chatbox.introduction");

    // Typing effect emits one character per tick (char-wise typewriter).
    // The old word-based split (on spaces) was incompatible with CJK text,
    // which has no spaces — Chinese appeared as one huge block. Iterating
    // code points (not UTF-16 units) keeps astral characters like emoji
    // intact.
    const chars = Array.from(introduction);
    for (const char of chars) {
      await sleep(40);
      updateLastMessage(char);
    }
  };

  useEffect(() => {
    setMessages((prev) => {
      const hasOnboarding =
        prev.length === 1 && prev[0].isWelcome && prev[0].showOnboardingActions;
      return hasOnboarding
        ? [{ ...prev[0], content: t("chatbox.introduction") }]
        : prev;
    });
  }, [i18n.language, t]);

  /** Send an example question from a welcome chip (PM review item 5). */
  const handleExampleClick = (question: string) => {
    if (isLoading) return;
    setNewMessage(question);
    handleSendMessage(question);
  };

  const handleOnboardingAction = async (action: string) => {
    if (action === "browse") {
      handleExampleClick(t("chatbox.exampleQuestions.1"));
      return;
    }
    if (!action.startsWith("budget:")) return;

    const budgetValue = Number(action.slice("budget:".length));
    if (!Number.isFinite(budgetValue) || budgetValue <= 0) {
      toast.error(t("chatbox.budgetInvalid"));
      return;
    }
    try {
      const history = await fetchHistory(getOrCreateUserId());
      const budgetLine = `MONTHLY BUDGET: $${budgetValue.toFixed(2)}`;
      if (hasMonthlyBudgetLine(history.context, budgetLine)) return;
      await addContext(
        getOrCreateUserId(),
        budgetLine
      );
      toast.success(
        t("chatbox.budgetSaved", { budget: budgetValue.toFixed(2) })
      );
    } catch (error) {
      console.error("Chatbox: budget onboarding failed", error);
      toast.error(t("chatbox.budgetSaveFailed"));
    }
  };

  // Chips should appear only after the welcome typewriter finishes; otherwise
  // a click can race with the final character update and lose the question.
  const introductionText = t("chatbox.introduction");

  const handleResetClick = () => {
    if (!isResetArmed) {
      setIsResetArmed(true);
      resetConfirmTimeoutRef.current = window.setTimeout(
        disarmResetConfirmation,
        RESET_CONFIRM_TIMEOUT_MS
      );
      return;
    }

    disarmResetConfirmation();
    handleReset(true);
  };

  /** Quick add-to-cart from a product card (D4), with server confirmation. */
  const handleAddToCart = async (product: ImageContent | string) => {
    if (cartAddInFlight) return;
    const productDetails =
      typeof product === "string"
        ? { productUrl: "", productName: product }
        : product;
    setCartAddInFlight(true);
    try {
      await addCartProduct(getOrCreateUserId(), productDetails);
      toast.success(t("cart.added", { item: productDetails.productName }));
      onCartChange?.();
    } catch (error) {
      console.error("Chatbox: direct cart add failed", error);
      toast.error(t("cart.addFailed"));
    } finally {
      setCartAddInFlight(false);
    }
  };

  useEffect(() => {
    const commandRef = requestCommandRef;
    if (!commandRef) return;
    commandRef.current = handleAddToCart;
    return () => {
      commandRef.current = null;
    };
  });

  const handleToggleFavorite = (product: ImageContent) => {
    setFavorites(toggleFavorite(product));
  };

  // Effects
  // Scroll management for the message list:
  //  - live mode (tab already visible): follow new content only when the user
  //    is already near the bottom, so reading history is never interrupted;
  //  - tab return: display:none wipes scrollTop, so either restore the exact
  //    offset the user left off at, or jump to the newest message if content
  //    arrived while the Messages tab was hidden.
  useEffect(() => {
    const el = messagesContainerRef.current;
    const count = messages.length;
    const becameVisible = visible && !prevVisibleRef.current;

    if (el) {
      if (becameVisible) {
        if (count > prevCountRef.current) {
          // Content arrived while hidden: show the latest assistant message.
          const targetIndex = lastAssistantIndex ?? count - 1;
          messageRefs.current[targetIndex]?.current?.scrollIntoView({
            behavior: "auto",
            block: "start",
          });
        } else {
          // Nothing new: put the list back exactly where the user left it.
          el.scrollTop = savedScrollTopRef.current;
        }
      } else if (visible && lastAssistantIndex !== null) {
        // The list renders in chronological order (flex-direction:
        // column — PM review item 1). Compute the distance from the
        // newest (bottom) edge; the column-reverse branch is kept only
        // for compatibility with themes that still reverse the list,
        // where scrollTop is negative toward OLDER messages.
        const reversed =
          getComputedStyle(el).flexDirection === "column-reverse";
        const distanceFromBottom = reversed
          ? Math.abs(Math.min(0, el.scrollTop))
          : el.scrollHeight - el.scrollTop - el.clientHeight;
        // Follow streaming/new content only when pinned near the bottom
        // (or on the very first messages), otherwise leave the viewport alone.
        if (
          prevCountRef.current === 0 ||
          distanceFromBottom <= NEAR_BOTTOM_PX
        ) {
          messageRefs.current[lastAssistantIndex]?.current?.scrollIntoView({
            behavior: "smooth",
            block: "start",
          });
        }
      }
    }

    prevCountRef.current = count;
    prevVisibleRef.current = visible;
  }, [messages, isLoading, visible, lastAssistantIndex]);

  // Return focus to the composer once a response finished streaming.
  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus();
    }
  }, [isLoading]);

  useEffect(() => {
    if (isOpen) {
      setHasBeenOpened(true);
    }
  }, [isOpen]);

  useEffect(() => {
    if (hasBeenOpened) {
      handleReset();
    }
  }, [hasBeenOpened]);

  useEffect(
    () => () => {
      if (resetConfirmTimeoutRef.current !== null) {
        window.clearTimeout(resetConfirmTimeoutRef.current);
      }
    },
    []
  );

  return (
    /* chatbox-shell: flex participant of .tab-panel — fills remaining space and
       passes min-height:0 down the chain. Without it the inner overflow-y:auto
       never activates because the wrapper grows with its content instead. */
    <div className="chatbox-shell">
      <div className="chatbox">
        <div className={`chatbox__support ${isOpen ? "chatbox--active" : ""}`}>
          {/* Header: title + Safety toggle */}
          <div className="chatbox__header">
            <h4 className="chatbox__heading--header">{t("chatbox.title")}</h4>
            <div className="chatbox__safety">
              <FormGroup>
                <FormControlLabel
                  control={
                    <CustomSwitch
                      checked={safetyEnabled}
                      onChange={toggleSafety}
                      size="small"
                      inputProps={{
                        "aria-label": t("chatbox.safety"),
                      }}
                    />
                  }
                  label={t("chatbox.safety")}
                />
              </FormGroup>
              {/* Microcopy so the toggle is perceivable (PM item 10 /
                  marketing A5): one line explaining what the state means. */}
              <p className="chatbox__safety-hint">
                {safetyEnabled
                  ? t("chatbox.safetyOnHint")
                  : t("chatbox.safetyOffHint")}
              </p>
            </div>
          </div>

          {/* Messages */}
          <div
            ref={messagesContainerRef}
            className="chatbox__messages"
            onScroll={(e) => {
              // Ignore scroll noise emitted while the Messages tab is hidden:
              // browsers clamp scrollTop of display:none containers, and
              // saving that would wipe the offset we need to restore later.
              if (e.currentTarget.offsetParent === null) return;
              savedScrollTopRef.current = e.currentTarget.scrollTop;
            }}
          >
            {/* Chronological order: oldest at the top, newest at the
                bottom, auto-scrolled into view by the scroll-management
                effect (PM review item 1 — the reversed render made new
                messages land above the fold). */}
            {messages.map((msg, index) => (
              <MessageItem
                key={index}
                role={msg.role}
                content={msg.content}
                productName={msg.productName}
                ref={messageRefs.current[index]}
                exampleQuestions={
                  msg.isWelcome && msg.content === introductionText
                    ? (t("chatbox.exampleQuestions", {
                        returnObjects: true,
                      }) as string[])
                    : undefined
                }
                onExampleClick={handleExampleClick}
                onActionClick={handleOnboardingAction}
                showOnboardingActions={msg.showOnboardingActions}
                onAddToCart={
                  msg.role === "image_row" ? handleAddToCart : undefined
                }
                cartAddInFlight={cartAddInFlight}
                onToggleFavorite={
                  msg.role === "image_row" ? handleToggleFavorite : undefined
                }
                isFavorite={
                  msg.role === "image_row" &&
                  (msg.content as ImageContent[]).some((product) =>
                    favorites.some(
                      (favorite) => favorite.productName === product.productName
                    )
                  )
                }
                isWelcome={msg.isWelcome}
                isHistory={msg.isHistory}
              />
            ))}
            {/* Slow-retrieval hint under the loader (PM item 3): appears
                when the first token hasn't arrived for a while. */}
            {isLoading && isSlow && (
              <div className="messages__slow-hint" role="status">
                {t(
                  isSlow === "third"
                    ? "errors.slowResponseThird"
                    : isSlow === "second"
                    ? "errors.slowResponseSecond"
                    : "errors.slowResponse"
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="chatbox__footer">
            {/* Image preview */}
            {previewImage && (
              <div style={{ position: "relative", display: "inline-block" }}>
                <img
                  src={previewImage}
                  alt="Preview"
                  style={{ width: "50px", height: "50px" }}
                />
                <button
                  type="button"
                  style={{
                    display: "inline-flex",
                    position: "absolute",
                    right: "-5px",
                    top: "-5px",
                    cursor: "pointer",
                    background: "transparent",
                    border: "none",
                    padding: 0,
                  }}
                  onClick={clearImage}
                  aria-label="Clear image"
                >
                  <FontAwesomeIcon icon={faTimesCircle} />
                </button>
              </div>
            )}

            {/* Input field */}
            <input
              ref={inputRef}
              type="text"
              className="input_test"
              placeholder={t("chatbox.placeholder")}
              value={newMessage}
              onChange={handleNewMessageChange}
              onKeyUp={handleKeyUp}
            />

            {/* Action buttons (real buttons for a11y: keyboard focusable,
                screen-reader labelled — PM review item 8) */}
            <div className="button-class">
              <SendIcon
                sx={{
                  color: isLoading ? "lightgray" : "#1d4ed8",
                  cursor: isLoading ? "not-allowed" : "pointer",
                }}
                onClick={isLoading ? () => {} : () => handleSendMessage()}
                fontSize="medium"
                aria-label={t("chatbox.sendLabel")}
              />
            </div>

            <div className="button-class">
              <CancelIcon
                sx={{ color: isResetArmed ? "#dc2626" : "#6b7280" }}
                onClick={handleResetClick}
                fontSize="medium"
                aria-label={t(
                  isResetArmed
                    ? "chatbox.resetConfirmLabel"
                    : "chatbox.resetLabel"
                )}
              />
            </div>

            <div className="button-class">
              <label
                htmlFor="image-upload"
                style={{ cursor: "pointer", display: "inline-flex" }}
                aria-label={t("chatbox.uploadLabel")}
                title={t("chatbox.uploadLabel")}
              >
                <UploadIcon sx={{ color: "#1d4ed8" }} fontSize="medium" />
              </label>
              <input
                style={{ display: "none" }}
                type="file"
                accept="image/*"
                id="image-upload"
                name="image"
                onChange={handleImageUpload}
              />
            </div>
          </div>
        </div>

        {/* Chatbox toggle button (hidden) */}
        <div className="chatbox__button" style={{ visibility: "hidden" }}>
          <button onClick={() => setIsOpen(!isOpen)}>
            <img
              src="https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Chat_icon.svg/44px-Chat_icon.svg.png"
              alt="Chat"
            />
          </button>
        </div>
      </div>
    </div>
  );
};

export default Chatbox;
