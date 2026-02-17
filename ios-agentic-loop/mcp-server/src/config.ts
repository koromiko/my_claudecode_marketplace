/**
 * Configuration loading for the MCP server.
 * Reads agentic-loop.config.yaml from the project root.
 */

import { readFileSync, existsSync } from "fs";
import { parse } from "yaml";

export interface AgenticConfig {
  simulator: {
    device: string;
    runtime: string;
    udid: string;
  };
  app: {
    bundle_id: string;
    extension_bundle_ids: string[];
    build_command: string;
    app_group: string;
  };
  idb: {
    action_delay_ms: number;
    describe_all_timeout_ms: number;
  };
  loop: {
    max_steps_per_goal: number;
    max_retries_per_action: number;
    verify_timeout_ms: number;
  };
  maestro: {
    output_dir: string;
    prefer_id_selectors: boolean;
    include_ai_assertions: boolean;
  };
  artifacts: {
    results_dir: string;
    keep_last_n_runs: number;
  };
}

export const DEFAULT_CONFIG: AgenticConfig = {
  simulator: { device: "iPhone 16 Pro", runtime: "iOS 18.2", udid: "auto" },
  app: { bundle_id: "", extension_bundle_ids: [], build_command: "", app_group: "" },
  idb: { action_delay_ms: 500, describe_all_timeout_ms: 5000 },
  loop: { max_steps_per_goal: 30, max_retries_per_action: 3, verify_timeout_ms: 2000 },
  maestro: { output_dir: "tests/maestro/flows", prefer_id_selectors: true, include_ai_assertions: true },
  artifacts: { results_dir: "tests/agentic/results", keep_last_n_runs: 10 },
};

function deepMerge<T extends Record<string, any>>(target: T, source: Record<string, any>): T {
  const result = { ...target };
  for (const key of Object.keys(source)) {
    if (
      source[key] &&
      typeof source[key] === "object" &&
      !Array.isArray(source[key]) &&
      target[key] &&
      typeof target[key] === "object" &&
      !Array.isArray(target[key])
    ) {
      (result as any)[key] = deepMerge(target[key], source[key]);
    } else {
      (result as any)[key] = source[key];
    }
  }
  return result;
}

export async function loadConfig(): Promise<AgenticConfig> {
  const configPath =
    process.env.AGENTIC_CONFIG_PATH || "agentic-loop.config.yaml";
  if (!existsSync(configPath)) {
    return { ...DEFAULT_CONFIG };
  }
  const raw = readFileSync(configPath, "utf-8");
  const parsed = parse(raw) ?? {};
  return deepMerge(DEFAULT_CONFIG, parsed);
}
