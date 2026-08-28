import { config } from "../config/appConfig";
import { authFetch } from "../lib/auth";

export type FreshnessConfig = { data_freshness_hours: number };

export const fetchFreshness = async (): Promise<FreshnessConfig> => {
  const response = await authFetch(getApiUrl("freshness"));
  if (!response.ok) throw new Error("Freshness fetch failed");
  return response.json();
};

export const saveFreshness = async (
  dataFreshnessHours: number
): Promise<FreshnessConfig> => {
  const response = await authFetch(getApiUrl("freshness"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data_freshness_hours: dataFreshnessHours }),
  });
  if (!response.ok) throw new Error("Freshness save failed");
  return response.json();
};

const getApiUrl = (endpoint: keyof AppConfig["api"]["endpoints"]) =>
  `${config.api.baseUrl}${config.api.endpoints[endpoint]}`;
