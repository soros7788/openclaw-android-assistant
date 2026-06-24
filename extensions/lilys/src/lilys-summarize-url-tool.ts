import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-runtime";
import { jsonResult, readStringParam } from "openclaw/plugin-sdk/provider-web-search";
import { Type } from "typebox";
import { summarizeUrl } from "./lilys-client.js";

const LilysSummarizeUrlSchema = Type.Object(
  {
    url: Type.String({ description: "URL of the content to summarize (YouTube video, article, PDF page, etc.)." }),
    language: Type.Optional(
      Type.String({ description: "Target language for the summary (e.g., 'zh', 'en', 'ko')." }),
    ),
    summaryLength: Type.Optional(
      Type.String({ description: "Summary length: 'short', 'medium', or 'long'." }),
    ),
    model: Type.Optional(
      Type.String({ description: "LilysAI model to use for summarization." }),
    ),
  },
  { additionalProperties: false },
);

export function createLilysSummarizeUrlTool(api: OpenClawPluginApi) {
  return {
    name: "lilys_summarize_url",
    label: "LilysAI Summarize URL",
    description:
      "Summarize content from a URL using LilysAI. Supports YouTube videos, articles, web pages, and more.",
    parameters: LilysSummarizeUrlSchema,
    execute: async (_toolCallId: string, rawParams: Record<string, unknown>) => {
      const url = readStringParam(rawParams, "url", { required: true });
      const language = readStringParam(rawParams, "language");
      const summaryLength = readStringParam(rawParams, "summaryLength");
      const model = readStringParam(rawParams, "model");

      const result = await summarizeUrl({
        cfg: api.config,
        url,
        language: language || undefined,
        summaryLength:
          summaryLength === "short" || summaryLength === "medium" || summaryLength === "long"
            ? summaryLength
            : undefined,
        model: model || undefined,
      });

      return jsonResult({
        requestId: result.requestId,
        title: result.title,
        summary: result.summary,
        keyPoints: result.keyPoints,
        sourceUrl: result.sourceUrl,
        status: result.status,
      });
    },
  };
}
