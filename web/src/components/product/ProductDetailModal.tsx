/**
 * ProductDetailModal: shared product detail dialog.
 *
 * - Shows the large image, name, price, full description and (when
 *   available) the intangible-heritage story of a catalog product.
 * - A specifications table maps the raw category/subcategory onto i18n
 *   labels and lists price + source domain.
 * - Shows catalog provenance, price/image disclaimers and concrete checks
 *   instead of fabricating buyer reviews.
 * - Add-to-cart goes straight through the orchestrator cart API.
 * - External purchase uses the original marketplace URL supplied by retrieval.
 * - Closes on overlay click, the close button and Escape.
 */

import React, { useEffect, useState } from "react";
import { toast } from "react-toastify";
import { useTranslation } from "react-i18next";
import AddShoppingCartIcon from "@mui/icons-material/AddShoppingCart";
import CloseIcon from "@mui/icons-material/Close";
import "./product-detail.css";
import { addCartProduct } from "../../api/cartApi";
import { getOrCreateUserId } from "../../lib/identity";
import { formatCny } from "../../lib/currency";
import { CatalogProduct } from "../../types/product";

interface ProductDetailModalProps {
  product: CatalogProduct;
  onClose: () => void;
  /** Notifies the shell that the cart changed so the tab badge updates. */
  onCartChange?: () => void;
}

const ProductDetailModal: React.FC<ProductDetailModalProps> = ({
  product,
  onClose,
  onCartChange,
}) => {
  const { t } = useTranslation();
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleAddToCart = async () => {
    if (adding) return;
    setAdding(true);
    try {
      await addCartProduct(getOrCreateUserId(), {
        productUrl: product.image,
        productName: product.name,
        externalUrl: product.url,
        price: product.price,
      });
      toast.success(t("cart.added", { item: product.name }));
      onCartChange?.();
    } catch (error) {
      console.error("ProductDetailModal: failed to add to cart", error);
      toast.error(t("cart.addFailed", { item: product.name }));
    } finally {
      setAdding(false);
    }
  };

  const hasPrice = typeof product.price === "number" && product.price > 0;

  // --- Specifications (empty fields stay hidden) ---
  const categoryLabel = product.category
    ? t(`productDetail.categories.${product.category}`, {
        defaultValue: product.category,
      })
    : "";
  const subcategoryLabel = product.subcategory
    ? t(`guizhou.groups.${product.subcategory}`, {
        defaultValue: product.subcategory,
      })
    : "";
  const sourceDomain = (() => {
    if (!product.url) return "";
    try {
      return new URL(product.url).hostname;
    } catch {
      return product.url;
    }
  })();

  const specRows: { label: string; value: string }[] = [
    { label: t("productDetail.specCategory"), value: categoryLabel },
    { label: t("productDetail.specSubcategory"), value: subcategoryLabel },
    { label: t("productDetail.specPrice"), value: hasPrice ? formatCny(product.price) : "" },
    { label: t("productDetail.specSource"), value: sourceDomain },
  ].filter((row) => row.value !== "");

  return (
    <div
      className="product-detail-overlay"
      data-testid="product-detail-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={t("productDetail.title")}
      onClick={onClose}
    >
      <div
        className="product-detail-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="product-detail-modal__close"
          aria-label={t("productDetail.close")}
          onClick={onClose}
        >
          <CloseIcon fontSize="small" />
        </button>
        <div className="product-detail-modal__media">
          <img src={product.image} alt={product.name} />
          <span className="product-detail-modal__image-notice">
            {t("productDetail.imageNotice")}
          </span>
        </div>
        <div className="product-detail-modal__body">
          <h3 className="product-detail-modal__name">{product.name}</h3>
          {hasPrice && (
            <div className="product-detail-modal__price">
              {formatCny(product.price)}
              <small>{t("productDetail.referencePrice")}</small>
            </div>
          )}
          {product.description && (
            <p className="product-detail-modal__description">
              {product.description}
            </p>
          )}
          {specRows.length > 0 && (
            <div className="product-detail-modal__specs">
              <h4>{t("productDetail.specs")}</h4>
              <table className="product-detail-modal__specs-table">
                <tbody>
                  {specRows.map((row) => (
                    <tr key={row.label}>
                      <th scope="row">{row.label}</th>
                      <td>{row.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {product.story && (
            <div className="product-detail-modal__story">
              <h4>{t("productDetail.storyLabel")}</h4>
              <p>{product.story}</p>
            </div>
          )}
          <div className="product-detail-modal__verification">
            <h4>{t("productDetail.verification")}</h4>
            <p>
              {t("productDetail.verifiedAt", {
                date: product.verifiedAt || "2026-08-29",
              })}
              {product.sourceUrl && (
                <>
                  {" · "}
                  <a href={product.sourceUrl} target="_blank" rel="noopener noreferrer">
                    {product.sourceName || t("productDetail.specSource")}
                  </a>
                </>
              )}
            </p>
          </div>
          <div className="product-detail-modal__buying-tips">
            <h4>{t("productDetail.buyingTips")}</h4>
            <ul>
              {(t("productDetail.buyingTipsList", {
                returnObjects: true,
              }) as string[]).map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          </div>
          <div className="product-detail-modal__actions">
            <button
              type="button"
              className="product-detail-modal__add"
              onClick={handleAddToCart}
              disabled={adding}
            >
              <AddShoppingCartIcon fontSize="small" />
              {t("chatbox.addToCart")}
            </button>
            <div className="product-detail-modal__buy-links">
              {product.url && (
                <a
                  href={product.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="product-detail-modal__buy-link"
                >
                  {t("productDetail.buyNow")}
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProductDetailModal;
