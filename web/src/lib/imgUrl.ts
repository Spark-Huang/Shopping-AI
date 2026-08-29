/**
 * Route external product images through the backend image proxy to avoid
 * hotlink protection and mixed-content blocking (http images on https pages).
 * Local/relative assets pass through unchanged.
 */
const PROXY_HOSTS = ["yiwugo.com", "ddimg.cn", "piaojia.cn"];

export const proxiedImage = (url: string | null | undefined): string => {
  if (!url) return "";
  if (!/^https?:\/\//i.test(url)) return url;
  const host = url.split("/")[2] ?? "";
  if (!PROXY_HOSTS.some((d) => host.includes(d))) return url;
  return `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/img?url=${encodeURIComponent(url)}`;
};
