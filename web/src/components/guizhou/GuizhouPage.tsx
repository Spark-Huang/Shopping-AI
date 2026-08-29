/**
 * GuizhouPage: the app-wide product discovery experience.
 *
 * - The whole application is Guizhou-focused; this is a general goods
 *   catalog, not a separate "Guizhou column".
 * - A horizontal, auto-scrolling carousel under the banner highlights the
 *   products; it pauses on hover/touch and wraps back to the start.
 * - Category chips (each with a small AI culture-tour button that hands a
 *   themed prompt to the chat agent) filter the product grid below.
 * - Clicking any card — carousel or grid — opens the shared
 *   ProductDetailModal with the full description, heritage story, cart
 *   action and external buy links.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "react-toastify";
import { useTranslation } from "react-i18next";
import AddShoppingCartIcon from "@mui/icons-material/AddShoppingCart";
import AutoStoriesIcon from "@mui/icons-material/AutoStories";
import RefreshIcon from "@mui/icons-material/Refresh";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import "./guizhou.css";
import { addCartProduct } from "../../api/cartApi";
import { fetchProducts } from "../../api/productsApi";
import { getOrCreateUserId } from "../../lib/identity";
import { formatCny } from "../../lib/currency";
import { CatalogProduct } from "../../types/product";
import ProductDetailModal from "../product/ProductDetailModal";

interface GuizhouPageProps {
  /** Notifies App that the cart changed so the tab badge updates. */
  onCartChange?: () => void;
  /** Hands a themed culture-tour prompt to the chat agent and jumps to it. */
  onTourStart?: (query: string) => void;
}

type LoadState = "loading" | "ready" | "error";

type FilterKey = "all" | "ethnic-wear" | "craft" | "food" | "drink";

export const FILTER_SUBCATEGORIES: Record<
  Exclude<FilterKey, "all">,
  string[]
> = {
  "ethnic-wear": ["苗银", "蜡染", "苗绣"],
  craft: ["苗银", "蜡染", "苗绣"],
  food: [
    "地方小吃",
    "调味酱",
    "酸汤底料",
    "刺梨饮品",
    "刺梨食品",
    "牛肉干",
    "波波糖",
    "折耳根食品",
  ],
  drink: [
    "酱香白酒",
    "董酒",
    "青酒",
    "贵州安酒",
    "都匀毛尖",
    "湖潭翠芽",
    "贵州绿宝石茶",
    "凤冈锌硒茶",
    "普安红茶",
  ],
};

function productMatchesFilter(
  product: CatalogProduct,
  filter: FilterKey
): boolean {
  if (filter === "all") return true;
  return FILTER_SUBCATEGORIES[filter].includes(product.subcategory);
}

/** Filter chips in display order, each paired with its culture-tour key. */
const FILTERS: { key: FilterKey; tourKey: string }[] = [
  { key: "all", tourKey: "overview" },
  { key: "ethnic-wear", tourKey: "batik" },
  { key: "craft", tourKey: "silver" },
  { key: "food", tourKey: "food" },
  { key: "drink", tourKey: "tea" },
];

/** Carousel auto-scroll cadence (ms). */
const CAROUSEL_INTERVAL_MS = 3200;

/** How many products the grid shows per shuffled batch. */
const GRID_BATCH_SIZE = 24;

/** Themes the AI idea generator cycles through at random. */
const AI_THEMES = [
  "苗疆银饰与刺绣",
  "山水茶饮",
  "节庆伴手礼",
  "酸辣风味美食",
  "侗乡手工器物",
  "梯田农耕风物",
  "非遗技艺文创",
  "黔山珍馐",
];

/** Picks a random generation theme, biased toward the active category. */
function pickTheme(filter: FilterKey): string {
  if (filter === "ethnic-wear") return "民族服饰灵感";
  if (filter === "craft") return "传统工艺文创";
  if (filter === "food") return "酸辣风味美食";
  if (filter === "drink") return "高山云雾茶酒";
  return AI_THEMES[Math.floor(Math.random() * AI_THEMES.length)];
}

/**
 * Deterministic seeded shuffle (Fisher-Yates over a mulberry32 PRNG) so the
 * "换一批" refresh button can re-shuffle the pool reproducibly per seed.
 */
function shuffleWithSeed<T>(items: T[], seed: number): T[] {
  const copy = [...items];
  let state = seed >>> 0;
  const rand = () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

const GuizhouPage: React.FC<GuizhouPageProps> = ({ onCartChange, onTourStart }) => {
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [filter, setFilter] = useState<FilterKey>("all");
  const [adding, setAdding] = useState<Set<string>>(new Set());
  const [detailProduct, setDetailProduct] = useState<CatalogProduct | null>(
    null
  );
  const [carouselPaused, setCarouselPaused] = useState(false);
  /** Shuffle seed — bumping it re-shuffles the visible grid batch. */
  const [shuffleSeed, setShuffleSeed] = useState(() =>
    Math.floor(Math.random() * 1e9)
  );
  /** Inspiration cards are selected only from grounded catalog records. */
  const [aiProducts, setAiProducts] = useState<CatalogProduct[]>([]);
  const [aiTheme, setAiTheme] = useState("");
  const [inspirationPulse, setInspirationPulse] = useState(false);
  const { t } = useTranslation();

  const carouselRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchProducts("guizhou");
      setProducts(data);
      setLoadState("ready");
    } catch (error) {
      console.error("GuizhouPage: failed to load products", error);
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Auto-scroll the carousel; native touch/wheel scrolling stays available,
  // hovering or touching pauses the timer, and the strip rewinds at the end.
  useEffect(() => {
    if (carouselPaused || products.length < 2) return;
    const id = window.setInterval(() => {
      const el = carouselRef.current;
      if (!el) return;
      const atEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - 8;
      if (atEnd) {
        el.scrollTo({ left: 0, behavior: "smooth" });
      } else {
        el.scrollBy({ left: el.clientWidth * 0.85, behavior: "smooth" });
      }
    }, CAROUSEL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [carouselPaused, products.length]);

  const handleAddToCart = async (product: CatalogProduct) => {
    if (adding.has(product.name)) return;
    setAdding((current) => new Set(current).add(product.name));
    try {
      await addCartProduct(getOrCreateUserId(), {
        productUrl: product.image,
        productName: product.name,
        externalUrl: product.url,
        price: product.price,
      });
      toast.success(t("guizhou.added", { item: product.name }));
      onCartChange?.();
    } catch (error) {
      console.error("GuizhouPage: failed to add to cart", error);
      toast.error(t("cart.addFailed", { item: product.name }));
    } finally {
      setAdding((current) => {
        const next = new Set(current);
        next.delete(product.name);
        return next;
      });
    }
  };

  // Card tiles are divs (they contain nested buttons, so they cannot be
  // <button> themselves); role/tabIndex/keydown keep them keyboard-reachable.
  const openDetail = (product: CatalogProduct) => setDetailProduct(product);
  const handleCardKeyDown = (
    product: CatalogProduct
  ): React.KeyboardEventHandler<HTMLDivElement> =>
    (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDetail(product);
      }
    };

  const handleTourClick = (tourKey: string) => {
    const query = t(`guizhou.tours.${tourKey}.query`);
    if (onTourStart) {
      onTourStart(query);
    } else {
      // Fallback: prefill nothing; caller without chat access is a bug.
      console.warn("GuizhouPage: onTourStart not provided");
    }
  };

  const handleGenerate = () => {
    const theme = pickTheme(filter);
    setAiTheme(theme);
    const pool =
      filter === "all"
        ? products
        : products.filter((product) => productMatchesFilter(product, filter));
    const generated = shuffleWithSeed(pool, Date.now()).slice(0, 6);
    setAiProducts(generated);
    setInspirationPulse(true);
    window.setTimeout(() => setInspirationPulse(false), 460);
    if (generated.length === 0) {
      toast.error(t("guizhou.aiGenerateFailed"));
    }
  };

  // Re-shuffle the whole pool whenever the seed changes; the grid then shows
  // a random batch so every "换一批" click surfaces fresh picks.
  const shuffled = useMemo(
    () => shuffleWithSeed(products, shuffleSeed),
    [products, shuffleSeed]
  );

  const batch = useMemo(() => {
    if (filter === "all") return shuffled.slice(0, GRID_BATCH_SIZE);
    return shuffleWithSeed(
      products.filter((product) => productMatchesFilter(product, filter)),
      shuffleSeed
    ).slice(0, GRID_BATCH_SIZE);
  }, [products, filter, shuffleSeed, shuffled]);

  return (
    <section className="guizhou-page" aria-label={t("guizhou.title")}>
      <div className="guizhou-page__header">
        <div className="guizhou-page__banner">
          <img
            src="/images/guizhou-banner.png"
            alt={t("guizhou.bannerAlt")}
            loading="lazy"
          />
        </div>
        <h4 className="guizhou-page__title">{t("guizhou.title")}</h4>
        <p className="guizhou-page__subtitle">{t("guizhou.subtitle")}</p>
      </div>

      <div className="guizhou-page__body">
        {loadState === "loading" && (
          <div className="guizhou-page__loading">{t("guizhou.loading")}</div>
        )}
        {loadState === "error" && (
          <div className="guizhou-page__error">{t("guizhou.error")}</div>
        )}
        {loadState === "ready" && (
          <>
            {/* Horizontal auto-scrolling product carousel */}
            {products.length > 0 && (
              <div className="guizhou-carousel">
                <h5 className="guizhou-page__group-title">
                  {t("guizhou.carouselTitle")}
                </h5>
                <div
                  className="guizhou-carousel__track"
                  ref={carouselRef}
                  onMouseEnter={() => setCarouselPaused(true)}
                  onMouseLeave={() => setCarouselPaused(false)}
                  onTouchStart={() => setCarouselPaused(true)}
                  onTouchEnd={() => setCarouselPaused(false)}
                >
                  {shuffled.map((product) => (
                    <button
                      type="button"
                      className="guizhou-carousel__card"
                      key={product.name}
                      aria-label={t("chatbox.viewProduct", {
                        name: product.name,
                      })}
                      onClick={() => setDetailProduct(product)}
                    >
                      <span className="guizhou-carousel__media">
                        <img
                          src={product.image}
                          alt={product.name}
                          loading="lazy"
                        />
                      </span>
                      <span className="guizhou-carousel__name">
                        {product.name}
                      </span>
                      <span className="guizhou-carousel__price">
                        {formatCny(product.price)}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Category filter chips with per-chip AI tour entries */}
            <div className="guizhou-page__filters">
              <h5 className="guizhou-page__group-title">
                {t("guizhou.filterTitle")}
              </h5>
              <div className="guizhou-page__filter-list">
                {FILTERS.map(({ key, tourKey }) => {
                  const label =
                    key === "all"
                      ? t("guizhou.filterAll")
                      : t(`guizhou.groups.${key}`);
                  return (
                    <div
                      key={key}
                      className={`guizhou-filter-chip${
                        filter === key ? " guizhou-filter-chip--active" : ""
                      }`}
                    >
                      <button
                        type="button"
                        className="guizhou-filter-chip__label"
                        aria-pressed={filter === key}
                        onClick={() => setFilter(key)}
                      >
                        {label}
                      </button>
                      <button
                        type="button"
                        className="guizhou-filter-chip__tour"
                        aria-label={t("guizhou.tourButton", { label })}
                        title={t("guizhou.tourButton", { label })}
                        onClick={() => handleTourClick(tourKey)}
                      >
                        <AutoStoriesIcon sx={{ fontSize: 14 }} />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* AI idea generator: endless LLM-generated inspiration cards */}
            <div className="guizhou-page__grid-header guizhou-page__ai-header">
              <h5 className="guizhou-page__group-title">
                <AutoAwesomeIcon sx={{ fontSize: 15, verticalAlign: "-2px" }} />{" "}
                {t("guizhou.aiTitle")}
                {aiTheme && (
                  <span className="guizhou-page__ai-theme">
                    · {t("guizhou.aiThemeLabel", { theme: aiTheme })}
                  </span>
                )}
              </h5>
              <button
                type="button"
                className={`guizhou-page__shuffle guizhou-page__ai-generate${
                  inspirationPulse ? " guizhou-page__ai-generate--pulse" : ""
                }`}
                onClick={handleGenerate}
              >
                <AutoAwesomeIcon sx={{ fontSize: 15 }} />
                {aiProducts.length > 0
                  ? t("guizhou.aiRegenerate")
                  : t("guizhou.aiGenerate")}
              </button>
            </div>
            {aiProducts.length > 0 && (
              <div className="guizhou-page__grid">
                {aiProducts.map((product, index) => (
                  <div
                    className="guizhou-card guizhou-card--clickable guizhou-card--ai"
                    key={`${product.name}-${index}`}
                    role="button"
                    tabIndex={0}
                    aria-label={t("chatbox.viewProduct", { name: product.name })}
                    onClick={() => openDetail(product)}
                    onKeyDown={handleCardKeyDown(product)}
                  >
                    <div className="guizhou-card__media">
                      <img
                        src={product.image}
                        alt={product.name}
                        loading="lazy"
                      />
                      <span className="guizhou-card__ai-badge">
                        <AutoAwesomeIcon sx={{ fontSize: 11 }} />
                        {t("guizhou.aiBadge")}
                      </span>
                    </div>
                    <div className="guizhou-card__body">
                      <div className="guizhou-card__name-row">
                        <span className="guizhou-card__name">{product.name}</span>
                      </div>
                      <p className="guizhou-card__description">
                        {product.description}
                      </p>
                      {product.story && (
                        <details className="guizhou-card__story">
                          <summary>{t("guizhou.storyLabel")}</summary>
                          <p>{product.story}</p>
                        </details>
                      )}
                      <div className="guizhou-card__footer">
                        <span className="guizhou-card__price">
                          {formatCny(product.price)}
                        </span>
                        <button
                          type="button"
                          className="guizhou-card__add"
                          disabled={adding.has(product.name)}
                          onClick={(event) => {
                            event.stopPropagation();
                            handleAddToCart(product);
                          }}
                        >
                          <AddShoppingCartIcon fontSize="small" />
                          {t("chatbox.addToCart")}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Product grid: a shuffled batch, refreshable via "换一批" */}
            <div className="guizhou-page__grid-header">
              <h5 className="guizhou-page__group-title">
                {filter === "all"
                  ? t("guizhou.picksTitle")
                  : t(`guizhou.groups.${filter}`)}
              </h5>
              <button
                type="button"
                className="guizhou-page__shuffle"
                onClick={() =>
                  setShuffleSeed((seed) => (seed + 1) % 1e9)
                }
              >
                <RefreshIcon sx={{ fontSize: 15 }} />
                {t("guizhou.shuffle")}
              </button>
            </div>
            <div className="guizhou-page__grid">
              {batch.map((product) => (
                <div
                  className="guizhou-card guizhou-card--clickable"
                  key={product.name}
                  role="button"
                  tabIndex={0}
                  aria-label={t("chatbox.viewProduct", { name: product.name })}
                  onClick={() => openDetail(product)}
                  onKeyDown={handleCardKeyDown(product)}
                >
                  <div className="guizhou-card__media">
                    <img
                      src={product.image}
                      alt={product.name}
                      loading="lazy"
                    />
                  </div>
                  <div className="guizhou-card__body">
                    <div className="guizhou-card__name-row">
                      <span className="guizhou-card__name">{product.name}</span>
                    </div>
                    <p className="guizhou-card__description">
                      {product.description}
                    </p>
                    {product.story && (
                      <details className="guizhou-card__story">
                        <summary>{t("guizhou.storyLabel")}</summary>
                        <p>{product.story}</p>
                      </details>
                    )}
                    <div className="guizhou-card__footer">
                      <span className="guizhou-card__price">
                        {formatCny(product.price)}
                      </span>
                      <button
                        type="button"
                        className="guizhou-card__add"
                        disabled={adding.has(product.name)}
                        onClick={(event) => {
                          event.stopPropagation();
                          handleAddToCart(product);
                        }}
                      >
                        <AddShoppingCartIcon fontSize="small" />
                        {t("chatbox.addToCart")}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {loadState === "ready" && batch.length === 0 && (
              <div className="guizhou-page__empty">
                {t("guizhou.filterEmpty")}
              </div>
            )}
          </>
        )}
      </div>

      {detailProduct && (
        <ProductDetailModal
          product={detailProduct}
          onClose={() => setDetailProduct(null)}
          onCartChange={onCartChange}
        />
      )}
    </section>
  );
};

export default GuizhouPage;
