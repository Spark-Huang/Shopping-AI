/**
 * Chat message component for displaying different types of messages
 */

import React from "react";
import FavoriteIcon from "@mui/icons-material/Favorite";
import FavoriteBorderOutlinedIcon from "@mui/icons-material/FavoriteBorderOutlined";
import ShareIcon from "@mui/icons-material/Share";
import { useTranslation } from "react-i18next";
import SafeHTML from "./SafeHtml";
import Loader from "./Loader";
import { ChatMessageProps, ImageContent, ImageRowContent } from "../../types/chat";
import { isSaysNo } from "../../lib/share";
import {
  createMarkdownConverter,
  preprocessAssistantContent,
} from "./messageParsing";
import { shareMessage } from "./messageActions";

const ChatMessage = React.forwardRef<HTMLDivElement, ChatMessageProps>(
  (
    {
      role,
      content,
      productName,
      isWelcome,
      exampleQuestions,
      onExampleClick,
      onAddToCart,
      onToggleFavorite,
      isFavorite,
      isHistory,
      cartAddInFlight,
    },
    ref
  ) => {
    const { t } = useTranslation();

    const isSaysNoMessage =
      role === "assistant" && typeof content === "string" && isSaysNo(content);

    const converter = createMarkdownConverter(role);

    // Don't render system messages
    if (role === "system") {
      return null;
    }

    // User message
    if (role === "user") {
      return (
        <div className={`messages__item messages__item--${role}`} ref={ref}>
          <SafeHTML html={content as string} />
        </div>
      );
    }

    // Assistant message
    if (role === "assistant") {
      if (content === "loader") {
        return (
          <div
            ref={ref}
            style={{
              display: "inline-flex",
              alignItems: "flex-start",
              gap: 8,
              marginTop: 10,
            }}
          >
            <span className="assistant-avatar" aria-hidden="true">
              <span className="assistant-avatar__face" />
            </span>
            <div className={`messages__item messages__item--${role}`}>
              <Loader />
            </div>
          </div>
        );
      }

      const processedContent = converter.makeHtml(
        preprocessAssistantContent(content as string)
      );

      // Clickable example-question chips (PM review item 5): when the
      // caller passes exampleQuestions, each entry is rendered as a chip
      // that sends the question on click.
      const showExamples = !!exampleQuestions && exampleQuestions.length > 0;
      return (
        <div
          ref={ref}
          style={{
            display: "inline-flex",
            alignItems: "flex-start",
            gap: 8,
            marginTop: 10,
          }}
        >
          <span
            className={`assistant-avatar${
              isSaysNoMessage ? " assistant-avatar--guard" : ""
            }`}
            aria-hidden="true"
          >
            <span className="assistant-avatar__face" />
          </span>
          <div
            className={`messages__item messages__item--${role}${
              isSaysNoMessage ? " messages__item--says-no" : ""
            }`}
          >
            {isHistory && (
              <div className="messages__item--history-badge">
                {t("chatbox.historyBadge")}
              </div>
            )}
            {isSaysNoMessage && (
              <div className="messages__item--says-no-badge">
                🛡️ {t("chatbox.saysNoBadge")}
              </div>
            )}
            <SafeHTML html={processedContent} />
            {isSaysNoMessage && (
              <button
                type="button"
                className="messages__item--share"
                onClick={() =>
                  shareMessage(
                    t("chatbox.saysNoShareText"),
                    t("chatbox.shareCopied"),
                    t("chatbox.shareFailed")
                  )
                }
              >
                <ShareIcon fontSize="small" />
                {t("chatbox.share")}
              </button>
            )}
            {showExamples && (
              <div className="messages__examples">
                {(exampleQuestions as string[]).map((question) => (
                  <button
                    key={question}
                    type="button"
                    className="messages__example-chip"
                    data-testid="example-chip"
                    onClick={() => onExampleClick?.(question)}
                  >
                    {question}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      );
    }

    // Image message (single product)
    if (role === "image") {
      const [imagePath, url, name, productRating] = (content as string).split(
        "|"
      );

      if (imagePath && url && name && productRating) {
        return (
          <div className={`messages__item messages__item--${role}`} ref={ref}>
            <img
              className="messages__item--image-img"
              src={imagePath}
              alt={name}
            />
            <div className="messages__item--image-box">
              <div className="messages__item--image-stars">{name}</div>
            </div>
          </div>
        );
      }
    }

    // Image row message (multiple products)
    if (role === "image_row") {
      const images = content as ImageRowContent;

      return (
        <div
          style={{
            width: "100%",
            height: "auto",
            display: "inline-flex",
            flexFlow: "row wrap",
          }}
        >
          {images.map((image: ImageContent, index: number) => (
            <div
              key={index}
              className={`messages__item messages__item--image`}
              ref={ref}
            >
              {/* Tile image links out to the original product (D4). */}
              <a
                href={image.externalUrl || image.productUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="messages__item--image-link"
                aria-label={t("chatbox.viewProduct", {
                  name: image.productName,
                })}
              >
                <img
                  className="messages__item--image-img-rowitem"
                  src={image.productUrl}
                  alt={image.productName}
                />
              </a>
              <div className="messages__item--image-box">
                <div className="messages__item--image-name">
                  {image.productName}
                </div>
                {(image.price != null || image.rating != null) && (
                  <div className="messages__item--image-meta">
                    {image.price != null && (
                      <span className="messages__item--image-price">
                        ${image.price.toFixed(2)}
                      </span>
                    )}
                    {image.rating != null && (
                      <span
                        className="messages__item--image-rating"
                        aria-label={t("chatbox.ratingLabel", {
                          rating: image.rating,
                        })}
                      >
                        ★ {image.rating.toFixed(1)}
                      </span>
                    )}
                  </div>
                )}
                {onAddToCart && (
                  <div className="messages__item--image-actions">
                    <button
                      type="button"
                      className="messages__item--image-add"
                      onClick={() => onAddToCart(image)}
                      disabled={cartAddInFlight}
                    >
                      {t("chatbox.addToCart")}
                    </button>
                    {onToggleFavorite && (
                      <button
                        type="button"
                        className="messages__item--image-favorite"
                        onClick={() => onToggleFavorite(image)}
                        aria-pressed={isFavorite}
                        aria-label={t("chatbox.toggleFavorite", {
                          name: image.productName,
                        })}
                      >
                        {isFavorite ? (
                          <FavoriteIcon fontSize="small" />
                        ) : (
                          <FavoriteBorderOutlinedIcon fontSize="small" />
                        )}
                      </button>
                    )}
                    <button
                      type="button"
                      className="messages__item--image-share"
                      onClick={() =>
                        shareMessage(
                          t("chatbox.productShareText", {
                            name: image.productName,
                            price:
                              image.price != null
                                ? `$${image.price.toFixed(2)}`
                                : "—",
                            rating:
                              image.rating != null
                                ? image.rating.toFixed(1)
                                : "—",
                          }),
                          t("chatbox.shareCopied"),
                          t("chatbox.shareFailed")
                        )
                      }
                      aria-label={t("chatbox.shareProduct", {
                        name: image.productName,
                      })}
                    >
                      <ShareIcon fontSize="small" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      );
    }

    // User uploaded image
    if (role === "user_image" && content) {
      return (
        <div className={`messages__item messages__item--${role}`} ref={ref}>
          <img
            className="messages__item--image-img"
            src={content as string}
            alt="User upload"
            style={{ borderRadius: "20px" }}
          />
        </div>
      );
    }

    return null;
  }
);

ChatMessage.displayName = "ChatMessage";

export default ChatMessage;
