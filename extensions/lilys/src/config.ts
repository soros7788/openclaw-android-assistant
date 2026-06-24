import type { OpenClawConfig } from "openclaw/plugin-sdk/config-contracts";
import { normalizeSecretInput } from "openclaw/plugin-sdk/secret-input";

export const DEFAULT_LILYS_BASE_URL = "https://tool.lilys.ai";

export function resolveLilysApiKey(cfg?: OpenClawConfig): string | undefined {
  if (!cfg) {
    return process.env.LILYS_API_KEY;
  }
  const pluginCfg = cfg.plugins?.entries?.lilys?.config as
    | { apiKey?: string | { $secret?: string }; baseUrl?: string }
    | undefined;
  const apiKey = pluginCfg?.apiKey;
  if (typeof apiKey === "string" && apiKey) {
    return normalizeSecretInput(apiKey);
  }
  if (apiKey && typeof apiKey === "object" && apiKey.$secret) {
    return normalizeSecretInput(apiKey.$secret);
  }
  const envKey = process.env.LILYS_API_KEY;
  if (envKey) {
    return normalizeSecretInput(envKey);
  }
  return undefined;
}

export function resolveLilysBaseUrl(cfg?: OpenClawConfig): string {
  if (!cfg) {
    return process.env.LILYS_BASE_URL || DEFAULT_LILYS_BASE_URL;
  }
  const pluginCfg = cfg.plugins?.entries?.lilys?.config as
    | { apiKey?: string; baseUrl?: string }
    | undefined;
  const baseUrl = pluginCfg?.baseUrl || process.env.LILYS_BASE_URL || DEFAULT_LILYS_BASE_URL;
  return baseUrl.replace(/\/+$/, "");
}
