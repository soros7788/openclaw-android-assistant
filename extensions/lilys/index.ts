import { definePluginEntry, type AnyAgentTool } from "openclaw/plugin-sdk/plugin-entry";
import { createLilysListModelsTool } from "./src/lilys-list-models-tool.js";
import {
  createLilysCreateSummaryTool,
  createLilysGetSummaryStatusTool,
} from "./src/lilys-summary-tools.js";
import { createLilysSummarizeUrlTool } from "./src/lilys-summarize-url-tool.js";

export default definePluginEntry({
  id: "lilys",
  name: "LilysAI Plugin",
  description: "LilysAI summarization and content analysis plugin",
  register(api) {
    api.registerTool(createLilysSummarizeUrlTool(api) as AnyAgentTool, {
      name: "lilys_summarize_url",
    });
    api.registerTool(createLilysCreateSummaryTool(api) as AnyAgentTool, {
      name: "lilys_create_summary",
    });
    api.registerTool(createLilysGetSummaryStatusTool(api) as AnyAgentTool, {
      name: "lilys_get_summary_status",
    });
    api.registerTool(createLilysListModelsTool(api) as AnyAgentTool, {
      name: "lilys_list_models",
    });
  },
});
