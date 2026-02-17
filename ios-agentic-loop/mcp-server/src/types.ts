import type { AgenticConfig } from "./config.js";

export interface ServerContext {
  config: AgenticConfig;
  udid: string;
  pluginRoot: string;
}
