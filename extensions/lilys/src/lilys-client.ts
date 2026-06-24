import type { OpenClawConfig } from "openclaw/plugin-sdk/config-contracts";
import { normalizeSecretInput } from "openclaw/plugin-sdk/secret-input";
import { wrapExternalContent } from "openclaw/plugin-sdk/security-runtime";
import { resolveLilysApiKey, resolveLilysBaseUrl } from "./config.js";

async function readJsonResponse(
  response: Response,
  label: string,
): Promise<Record<string, unknown>> {
  try {
    return (await response.json()) as Record<string, unknown>;
  } catch (cause) {
    throw new Error(`${label}: malformed JSON response`, { cause });
  }
}

export type LilysSummaryParams = {
  cfg?: OpenClawConfig;
  url: string;
  model?: string;
  language?: string;
  summaryLength?: "short" | "medium" | "long";
};

export type LilysSummaryResult = {
  requestId: string;
  status: string;
  title?: string;
  summary?: string;
  keyPoints?: string[];
  sourceUrl?: string;
};

export type LilysModel = {
  id: string;
  name: string;
  description?: string;
};

async function lilysRequest(
  params: {
    baseUrl: string;
    apiKey: string;
    path: string;
    method: "GET" | "POST";
    body?: Record<string, unknown>;
    errorLabel: string;
  },
): Promise<Record<string, unknown>> {
  const url = `${params.baseUrl}/${params.path.replace(/^\/+/, "")}`;
  const apiKey = normalizeSecretInput(params.apiKey);

  const init: RequestInit = {
    method: params.method,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
  };
  if (params.body) {
    init.body = JSON.stringify(params.body);
  }

  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = response.statusText || "request failed";
    try {
      const payload = await readJsonResponse(response, params.errorLabel);
      if (typeof payload.error === "string") {
        detail = payload.error;
      } else if (typeof payload.message === "string") {
        detail = payload.message;
      }
    } catch {
      // ignore
    }
    throw new Error(
      `${params.errorLabel} API error (${response.status}): ${wrapExternalContent(detail, { source: "lilys", includeWarning: false })}`,
    );
  }
  return await readJsonResponse(response, params.errorLabel);
}

export async function createLilysSummary(
  params: LilysSummaryParams,
): Promise<{ requestId: string; status: string }> {
  const apiKey = resolveLilysApiKey(params.cfg);
  if (!apiKey) {
    throw new Error(
      "LilysAI needs an API key. Set LILYS_API_KEY in the Gateway environment, or configure plugins.entries.lilys.config.apiKey.",
    );
  }
  const baseUrl = resolveLilysBaseUrl(params.cfg);

  const body: Record<string, unknown> = {
    url: params.url,
  };
  if (params.model) {
    body.model = params.model;
  }
  if (params.language) {
    body.language = params.language;
  }
  if (params.summaryLength) {
    body.summaryLength = params.summaryLength;
  }

  const payload = await lilysRequest({
    baseUrl,
    apiKey,
    path: "summaries",
    method: "POST",
    body,
    errorLabel: "LilysAI Create Summary",
  });

  const data = (payload.data || payload) as Record<string, unknown>;
  return {
    requestId: String(data.requestId || data.id || ""),
    status: String(data.status || "pending"),
  };
}

export async function getLilysSummaryStatus(
  params: { cfg?: OpenClawConfig; requestId: string },
): Promise<LilysSummaryResult> {
  const apiKey = resolveLilysApiKey(params.cfg);
  if (!apiKey) {
    throw new Error(
      "LilysAI needs an API key. Set LILYS_API_KEY in the Gateway environment, or configure plugins.entries.lilys.config.apiKey.",
    );
  }
  const baseUrl = resolveLilysBaseUrl(params.cfg);

  const payload = await lilysRequest({
    baseUrl,
    apiKey,
    path: `summaries/${encodeURIComponent(params.requestId)}`,
    method: "GET",
    errorLabel: "LilysAI Summary Status",
  });

  const data = (payload.data || payload) as Record<string, unknown>;
  const summaryNote = (data.summaryNote || data) as Record<string, unknown>;

  return {
    requestId: String(data.requestId || params.requestId),
    status: String(data.status || summaryNote.status || "unknown"),
    title: typeof summaryNote.title === "string" ? summaryNote.title : undefined,
    summary: typeof summaryNote.summary === "string" ? summaryNote.summary : undefined,
    keyPoints: Array.isArray(summaryNote.keyPoints)
      ? (summaryNote.keyPoints as string[])
      : undefined,
    sourceUrl: typeof summaryNote.sourceUrl === "string" ? summaryNote.sourceUrl : undefined,
  };
}

export async function listLilysModels(params: {
  cfg?: OpenClawConfig;
}): Promise<LilysModel[]> {
  const apiKey = resolveLilysApiKey(params.cfg);
  if (!apiKey) {
    throw new Error(
      "LilysAI needs an API key. Set LILYS_API_KEY in the Gateway environment, or configure plugins.entries.lilys.config.apiKey.",
    );
  }
  const baseUrl = resolveLilysBaseUrl(params.cfg);

  const payload = await lilysRequest({
    baseUrl,
    apiKey,
    path: "models",
    method: "GET",
    errorLabel: "LilysAI List Models",
  });

  const data = (payload.data || payload) as Record<string, unknown>;
  const models = Array.isArray(data.models) ? data.models : Array.isArray(data) ? data : [];

  return models
    .map((m: unknown) => {
      if (!m || typeof m !== "object") return null;
      const model = m as Record<string, unknown>;
      return {
        id: String(model.id || model.modelId || ""),
        name: String(model.name || model.displayName || ""),
        description:
          typeof model.description === "string" ? model.description : undefined,
      };
    })
    .filter((m): m is LilysModel => m !== null && Boolean(m.id));
}

export async function summarizeUrl(
  params: LilysSummaryParams & { pollIntervalMs?: number; maxPolls?: number },
): Promise<LilysSummaryResult> {
  const { requestId } = await createLilysSummary(params);
  const pollInterval = params.pollIntervalMs || 3000;
  const maxPolls = params.maxPolls || 60;

  for (let i = 0; i < maxPolls; i++) {
    await new Promise((resolve) => setTimeout(resolve, pollInterval));
    const result = await getLilysSummaryStatus({ cfg: params.cfg, requestId });
    if (result.status === "completed" || result.status === "done" || result.status === "success") {
      return result;
    }
    if (result.status === "failed" || result.status === "error") {
      throw new Error(`LilysAI summary failed: ${result.status}`);
    }
  }

  throw new Error("LilysAI summary timed out");
}
