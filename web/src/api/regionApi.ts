import { config, getApiUrl, type AppConfig } from "../config/appConfig";
import { authFetch } from "../lib/auth";

export type RegionConfig = { region: string };
export const SHOPPING_REGIONS = [
  "贵州",
  "云南",
  "四川",
  "重庆",
  "广东",
  "北京",
  "上海",
] as const;

export const fetchRegion = async (): Promise<RegionConfig> => {
  const response = await authFetch(getApiUrl("region"));
  if (!response.ok) throw new Error("Region fetch failed");
  return response.json();
};

export const saveRegion = async (region: string): Promise<RegionConfig> => {
  const response = await authFetch(getApiUrl("region"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region }),
  });
  if (!response.ok) throw new Error("Region save failed");
  return response.json();
};
