import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-runtime";
import { jsonResult } from "openclaw/plugin-sdk/provider-web-search";
import { Type } from "typebox";
import { listLilysModels } from "./lilys-client.js";

const LilysListModelsSchema = Type.Object({}, { additionalProperties: false });

export function createLilysListModelsTool(api: OpenClawPluginApi) {
  return {
    name: "lilys_list_models",
    label: "LilysAI List Models",
    description: "List available summarization models on LilysAI.",
    parameters: LilysListModelsSchema,
    execute: async () => {
      const models = await listLilysModels({ cfg: api.config });
      return jsonResult({ models });
    },
  };
}
