import React, { useState, useEffect, useRef } from "react";
import { toast } from "react-toastify";
import SendIcon from "@mui/icons-material/Send";
import CancelIcon from "@mui/icons-material/Cancel";
import UploadIcon from "@mui/icons-material/Upload";
import HistoryIcon from "@mui/icons-material/History";
import AddCommentIcon from "@mui/icons-material/AddComment";
import DeleteIcon from "@mui/icons-material/DeleteOutline";
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
import { addCartProduct } from "../../api/cartApi";
import {
  createChatSession,
  deleteChatSession,
  fetchSessionMessages,
  listChatSessions,
  type SessionMessage,
} from "../../api/historyApi";
import { useTranslation } from "react-i18next";
import {
  convertToBase64,
  createImagePreview,
  validateImageFile,
} from "./chatInput";
import { readChatStream } from "./ChatWindow.useStream";
import { parseImagesPayload } from "../../lib/images";
import { scheduleSession, sleep } from "./streamSession";
import type { ChatMessage, SessionSummary } from "./ChatWindow.types";

/**
 * Main chatbox component for 贵客来 (Guikelai).
 */

/** How close (px) to the bottom counts as "pinned", for auto-follow scrolling. */
const NEAR_BOTTOM_PX = 80;

const RESET_CONFIRM_TIMEOUT_MS = 3000;

const Chatbox: React.FC<ChatboxProps> = ({
  requestCommandRef,
  requestTourRef,
  requestNewChatRef,
  onCartChange,
  visible = true,
  safetyEnabled,
  onSafetyChange,
  dialectEnabled = false,
}) => {
  const { t, i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState<boolean>(true);
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
  const [chatSessions, setChatSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
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
  // React StrictMode may replay mount effects in development. Guard the
  // initial history/welcome load so a replay cannot append duplicate bubbles.
  const initialConversationLoadedRef = useRef(false);

  const disarmResetConfirmation = () => {
    if (resetConfirmTimeoutRef.current !== null) {
      window.clearTimeout(resetConfirmTimeoutRef.current);
      resetConfirmTimeoutRef.current = null;
    }
    setIsResetArmed(false);
  };

  const showWelcome = async () => {
    const introduction = t("chatbox.introduction");
    setMessages([
      {
        role: "assistant",
        content: introduction,
        productName: "",
        isWelcome: true,
      },
    ]);
    messageRefs.current = [React.createRef<HTMLDivElement>()];
    setLastAssistantIndex(0);
  };

  const refreshSessions = async (userId: number) => {
    try {
      setChatSessions(await listChatSessions(userId));
    } catch (error) {
      console.warn("Chatbox: session list unavailable", error);
      setChatSessions([]);
    }
  };

  useEffect(() => {
    void refreshSessions(getOrCreateUserId());
  }, []);

  const handleNewSession = async () => {
    if (isLoading) return;
    try {
      const created = await createChatSession(getOrCreateUserId());
      setChatSessions((previous) => [
        created,
        ...previous.filter((item) => item.id !== created.id),
      ]);
      setActiveSessionId(created.id);
      setIsHistoryOpen(false);
      disarmResetConfirmation();
      setImage("");
      setPreviewImage("");
      await showWelcome();
    } catch {
      toast.error(t("sessions.loadFailed"));
    }
  };

  const sessionMessagesToChatMessages = (
    sessionMessages: SessionMessage[]
  ): ChatMessage[] =>
    sessionMessages.flatMap<ChatMessage>((item) => {
      const baseMessage = {
        content: item.content,
        productName: "",
        isWelcome: false,
        isHistory: true,
      };
      if (item.role !== "assistant" || !item.products) {
        return [{ ...baseMessage, role: item.role }];
      }
      return [
        { ...baseMessage, role: item.role },
        {
          ...baseMessage,
          role: "image_row",
          content: parseImagesPayload(item.products),
        },
      ];
    });

  const loadSession = async (sessionId: number) => {
    if (isLoading) return;
    try {
      const sessionMessages = await fetchSessionMessages(getOrCreateUserId(), sessionId);
      setActiveSessionId(sessionId);
      setIsHistoryOpen(false);
      disarmResetConfirmation();
      setImage("");
      setPreviewImage("");
      setMessages(sessionMessagesToChatMessages(sessionMessages));
    } catch {
      toast.error(t("sessions.loadFailed"));
    }
  };

  const loadInitialConversation = async () => {
    try {
      const sessions = await listChatSessions(getOrCreateUserId());
      const latestSession = [...sessions].sort((first, second) => {
        const firstTime = Date.parse(first.updated_at ?? first.created_at ?? "");
        const secondTime = Date.parse(second.updated_at ?? second.created_at ?? "");
        if (!Number.isNaN(firstTime) && !Number.isNaN(secondTime)) {
          return secondTime - firstTime;
        }
        return 0;
      })[0];
      if (!latestSession) {
        await showWelcome();
        return;
      }

      const sessionMessages = await fetchSessionMessages(
        getOrCreateUserId(),
        latestSession.id
      );
      const lastAssistantIndex = [...sessionMessages]
        .reverse()
        .findIndex((item) => item.role === "assistant");
      if (lastAssistantIndex === -1) {
        await showWelcome();
        return;
      }
      const assistantIndex = sessionMessages.length - 1 - lastAssistantIndex;
      let userIndex = -1;
      for (let index = assistantIndex - 1; index >= 0; index -= 1) {
        if (sessionMessages[index].role === "user") {
          userIndex = index;
          break;
        }
      }
      const startIndex = userIndex === -1 ? assistantIndex : userIndex;
      setActiveSessionId(latestSession.id);
      setMessages(
        sessionMessagesToChatMessages(sessionMessages.slice(startIndex, assistantIndex + 1))
      );
    } catch (error) {
      console.warn("Chatbox: latest conversation replay skipped", error);
      await showWelcome();
    }
  };

  const handleDeleteSession = async (sessionId: number) => {
    try {
      await deleteChatSession(getOrCreateUserId(), sessionId);
      setChatSessions((previous) => previous.filter((item) => item.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        await showWelcome();
      }
    } catch {
      toast.error(t("sessions.deleteFailed"));
    }
  };

  // Event handlers
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
    isHistory: boolean = false
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
        dialect: dialectEnabled,
        session_id: activeSessionId,
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
   *  - mount (userInitiated=false): show only the final user/assistant turn
   *    from the latest session. Empty/failed lookup falls through to the
   *    welcome flow.
   *  - Reset button (userInitiated=true): explicit fresh start — drop the
   *    persistent user id (next message mints a new user) and show the welcome.
   */
  const handleReset = async (userInitiated: boolean = false) => {
    setMessages([]);
    setImage("");
    setPreviewImage("");
    if (userInitiated) {
      clearUserIdentity();
    }
    setActiveSessionId(null);
    if (userInitiated) {
      await showWelcome();
    }
  };

  useEffect(() => {
    setMessages((prev) => {
      const hasOnboarding = prev.length === 1 && prev[0].isWelcome;
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

  // Culture-tour handoff: the Guizhou page calls this ref with a themed
  // prompt; sending it through the normal pipeline keeps the question in
  // the transcript so the reply is grounded.
  useEffect(() => {
    const tourRef = requestTourRef;
    if (!tourRef) return;
    tourRef.current = handleSendMessage;
    return () => {
      tourRef.current = null;
    };
  });

  // New-chat handoff: the Navbar "more choices" menu calls this ref to
  // start a fresh conversation (explicit reset drops the user identity).
  useEffect(() => {
    const newChatRef = requestNewChatRef;
    if (!newChatRef) return;
    newChatRef.current = () => handleReset(true);
    return () => {
      newChatRef.current = null;
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
    if (!isOpen || initialConversationLoadedRef.current) return;
    initialConversationLoadedRef.current = true;
    void loadInitialConversation();
  }, [isOpen]);

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
          {/* Header */}
          <div className="chatbox__header">
            <div className="chatbox__header-left">
              <button
                type="button"
                className="session-history__toggle"
                aria-label={t("sessions.toggle")}
                title={t("sessions.toggle")}
                onClick={() => setIsHistoryOpen((open) => !open)}
              >
                <HistoryIcon fontSize="small" />
              </button>
              <h4 className="chatbox__heading--header">{t("chatbox.title")}</h4>
            </div>
            <button
              type="button"
              className="session-history__new"
              aria-label={t("sessions.new")}
              title={t("sessions.new")}
              onClick={handleNewSession}
            >
              <AddCommentIcon fontSize="small" />
            </button>
          </div>
          {isHistoryOpen && (
            <div className="session-history" data-testid="session-history">
              <button type="button" onClick={handleNewSession}>
                {t("sessions.new")}
              </button>
              <ul>
                {chatSessions.map((item) => (
                  <li key={item.id} className={item.id === activeSessionId ? "active" : ""}>
                    <button type="button" onClick={() => loadSession(item.id)}>
                      {item.title || t("sessions.untitled")}
                    </button>
                    <button
                      type="button"
                      aria-label={t("sessions.delete", {
                        title: item.title || t("sessions.untitled"),
                      })}
                      onClick={() => handleDeleteSession(item.id)}
                    >
                      <DeleteIcon fontSize="small" />
                    </button>
                  </li>
                ))}
              </ul>
              {chatSessions.length === 0 && (
                <p className="session-history__empty">{t("sessions.empty")}</p>
              )}
            </div>
          )}

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
                  msg.isWelcome
                    ? (t("chatbox.exampleQuestions", {
                        returnObjects: true,
                      }) as string[])
                    : undefined
                }
                onExampleClick={handleExampleClick}
                onAddToCart={
                  msg.role === "image_row" ? handleAddToCart : undefined
                }
                cartAddInFlight={cartAddInFlight}
                onCartChange={onCartChange}
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

          {/* Footer: unified pill composer with side toolbar */}
          <div className="chatbox__footer">
            {/* Image preview */}
            {previewImage && (
              <div className="chatbox__preview">
                <img src={previewImage} alt="Preview" />
                <button
                  type="button"
                  className="chatbox__preview-clear"
                  onClick={clearImage}
                  aria-label="Clear image"
                >
                  <FontAwesomeIcon icon={faTimesCircle} />
                </button>
              </div>
            )}

            <div className="chatbox__footer-row">
              {/* Composer pill: transparent input + round brand send button */}
              <div className="chatbox__composer">
                <input
                  ref={inputRef}
                  type="text"
                  className="chatbox__composer-input"
                  placeholder={t("chatbox.placeholder")}
                  aria-label={t("chatbox.placeholder")}
                  value={newMessage}
                  onChange={handleNewMessageChange}
                  onKeyUp={handleKeyUp}
                />
                <button
                  type="button"
                  className="chatbox__composer-send"
                  onClick={isLoading ? () => {} : () => handleSendMessage()}
                  disabled={isLoading}
                  aria-label={t("chatbox.sendLabel")}
                >
                  <SendIcon sx={{ color: "#ffffff", fontSize: 18 }} />
                </button>
              </div>

              {/* Side toolbar: image upload + reset (two-step confirm) */}
              <div className="chatbox__toolbar">
                <label
                  htmlFor="image-upload"
                  className="chatbox__tool chatbox__tool--upload"
                  aria-label={t("chatbox.uploadLabel")}
                  title={t("chatbox.uploadLabel")}
                >
                  <UploadIcon sx={{ fontSize: 20 }} />
                </label>
                <input
                  style={{ display: "none" }}
                  type="file"
                  accept="image/*"
                  id="image-upload"
                  name="image"
                  onChange={handleImageUpload}
                />
                <button
                  type="button"
                  className="chatbox__tool chatbox__tool--reset"
                  onClick={handleResetClick}
                  aria-label={t(
                    isResetArmed
                      ? "chatbox.resetConfirmLabel"
                      : "chatbox.resetLabel"
                  )}
                >
                  <CancelIcon
                    sx={{ fontSize: 20, color: isResetArmed ? "#dc2626" : "inherit" }}
                  />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Chatbox toggle button (hidden) */}
        <div className="chatbox__button" style={{ visibility: "hidden" }}>
          <button onClick={() => setIsOpen(!isOpen)}>
            <img src="/images/logo-guikelai.png" alt={t("brand.name")} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default Chatbox;
