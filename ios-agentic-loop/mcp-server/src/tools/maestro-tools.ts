/**
 * Maestro tool definitions for the MCP server.
 * Provides test execution and flow export tools.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";
import { stringify } from "yaml";
import type { ServerContext } from "../types.js";
import { execCommand } from "../utils/exec-command.js";
import { parseMaestroOutput } from "../utils/maestro-parser.js";

export interface MaestroRunParams {
  flow_path: string;
  continuous?: boolean;
  include_tags?: string[];
}

export interface MaestroRunResult {
  success: boolean;
  total_flows: number;
  passed: number;
  failed: number;
  failures: MaestroFailure[];
}

export interface MaestroFailure {
  flow_name: string;
  step_number: number;
  error: string;
}

export interface ActionLogEntry {
  step: number;
  action: string;
  x?: number;
  y?: number;
  text?: string;
  label?: string;
  type?: string;
  a11y_id?: string;
  verified: boolean;
}

export interface ExportFlowParams {
  action_log: ActionLogEntry[];
  flow_name: string;
  output_dir?: string;
}

export interface ExportFlowResult {
  flow_path: string;
  steps_count: number;
}

export function registerMaestroTools(server: McpServer, ctx: ServerContext): void {
  // 1. maestro_run — Run Maestro test flows
  server.registerTool("maestro_run", {
    description: "Run Maestro test flows. Returns pass/fail results with failure details.",
    inputSchema: {
      flow_path: z.string().describe("Path to flow file or directory"),
      continuous: z.boolean().optional().describe("Re-run on file changes"),
      include_tags: z.array(z.string()).optional().describe("Only run flows with these tags"),
    },
  }, async ({ flow_path, continuous, include_tags }) => {
    const args = ["test", flow_path];
    if (continuous) args.push("--continuous");
    if (include_tags?.length) args.push("--include-tags", include_tags.join(","));

    try {
      const { stdout } = await execCommand("maestro", args, { timeoutMs: 300_000 });
      const result = parseMaestroOutput(stdout);
      return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
    } catch (err: any) {
      if (err.stdout) {
        const result = parseMaestroOutput(err.stdout);
        return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
      }
      throw err;
    }
  });

  // 2. maestro_export_flow — Convert action log to Maestro YAML flow
  server.registerTool("maestro_export_flow", {
    description: "Convert an action log (from idb exploration) into a Maestro YAML flow. Uses selector priority: id > text > point coordinates.",
    inputSchema: {
      action_log: z.array(z.object({
        step: z.number(),
        action: z.string(),
        x: z.number().optional(),
        y: z.number().optional(),
        text: z.string().optional(),
        label: z.string().optional(),
        type: z.string().optional(),
        a11y_id: z.string().optional(),
        verified: z.boolean(),
      })).describe("Array of action log entries from exploration"),
      flow_name: z.string().describe("Name for the generated flow"),
      output_dir: z.string().optional().describe("Output directory (default: from config)"),
    },
  }, async ({ action_log, flow_name, output_dir }) => {
    const dir = output_dir ?? ctx.config.maestro.output_dir;
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });

    const steps: any[] = [
      { launchApp: { appId: ctx.config.app.bundle_id, clearState: true } },
    ];

    for (const entry of action_log) {
      if (entry.action === "tap") {
        if (entry.a11y_id) {
          steps.push({ tapOn: { id: entry.a11y_id } });
        } else if (entry.label) {
          steps.push({ tapOn: { text: entry.label } });
        } else if (entry.x != null && entry.y != null) {
          const xPct = Math.round((entry.x / 393) * 100);
          const yPct = Math.round((entry.y / 852) * 100);
          steps.push({ tapOn: { point: `${xPct}%,${yPct}%` } });
        }
      } else if (entry.action === "text" && entry.text) {
        steps.push({ inputText: entry.text });
      } else if (entry.action === "swipe") {
        if (entry.y != null && entry.x != null) {
          steps.push({ scroll: {} });
        }
      } else if (entry.action === "key") {
        steps.push({ pressKey: entry.text ?? "enter" });
      }
    }

    const flowContent = `appId: ${ctx.config.app.bundle_id}\nname: ${flow_name}\ntags:\n  - regression\n  - generated\n---\n${stringify(steps)}`;
    const flowPath = join(dir, `${flow_name.replace(/\s+/g, "_").toLowerCase()}.yaml`);
    writeFileSync(flowPath, flowContent);

    return { content: [{ type: "text" as const, text: `Flow exported to ${flowPath} (${steps.length} steps)` }] };
  });
}
