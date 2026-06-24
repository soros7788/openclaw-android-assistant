import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-runtime";
import { jsonResult, readStringParam } from "openclaw/plugin-sdk/provider-web-search";
import { Type } from "typebox";
import { createLilysSummary, getLilysSummaryStatus } from "./lilys-client.js";

const LilysCreateSummarySchema = Type.Object(
  {
    url: Type.String({ description: "URL of the content to summarize." }),
    language: Type.Optional(
      Type.String({ description: "Target language for the summary." }),
    ),
    summaryLength: Type.Optional(
      Type.String({ description: "Summary length: 'short', 'medium', or 'long'." }),
    ),
    model: Type.Optional(
      Type.String({ description: "LilysAI model to use." }),
    ),
  },
  { additionalProperties: false },
);

export function createLilysCreateSummaryTool(api: OpenClawPluginApi) {
  return {
    name: "lilys_create_summary",
    label: "LilysAI Create Summary",
    description:
      "Start a summarization task on LilysAI. Returns a requestId that can be used with lilys_get_summary_status.",
    parameters: LilysCreateSummarySchema,
    execute: async (_toolCallId: string, rawParams: Record<string, unknown>) => {
      const url = readStringParam(rawParams, "url", { required: true });
      const language = readStringParam(rawParams, "language");
      const summaryLength = readStringParam(rawParams, "summaryLength");
      const model = readStringParam(rawParams, "model");

      const result = await createLilysSummary({
        cfg: api.config,
        url,
        language: language || undefined,
        summaryLength:
          summaryLength === "short" || summaryLength === "medium" || summaryLength === "long"
            ? summaryLength
            : undefined,
        model: model || undefined,
      });

      return jsonResult(result);
    },
  };
}

const LilysGetSummaryStatusSchema = Type.Object(
  {
    requestId: Type.String({ description: "The summary request ID from lilys_create_summary." }),
  },
  { additionalProperties: false },
);

export function createLilysGetSummaryStatusTool(api: OpenClawPluginApi) {
  return {
    name: "lilys_get_summary_status",
    label: "LilysAI Get Summary Status",
    description: "Check the status of a LilysAI summarization task by requestId.",
    parameters: LilysGetSummaryStatusSchema,
    execute: async (_toolCallId: string, rawParams: Record<string, unknown>) => {
      const requestId = readStringParam(rawParams, "requestId", { required: true });

      const result = await getLilysSummaryStatus({
        cfg: api.config,
        requestId,
      });

      return jsonResult(result);
    },
  };
}
