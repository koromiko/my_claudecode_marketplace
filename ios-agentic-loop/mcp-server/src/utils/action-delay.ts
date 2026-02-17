import type { AgenticConfig } from "../config.js";

export function actionDelay(config: AgenticConfig): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, config.idb.action_delay_ms));
}
