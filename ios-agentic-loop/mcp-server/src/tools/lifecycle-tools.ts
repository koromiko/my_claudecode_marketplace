/**
 * App lifecycle tool definitions for the MCP server.
 * Provides launch, terminate, install, and build+launch tools.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { join } from "path";
import type { ServerContext } from "../types.js";
import { execCommand, execShell } from "../utils/exec-command.js";

export interface LaunchParams {
  bundle_id: string;
}

export interface TerminateParams {
  bundle_id: string;
}

export interface InstallParams {
  app_path: string;
}

export interface BuildAndLaunchParams {
  configuration?: "Debug" | "Release";
}

export interface BuildAndLaunchResult {
  build_success: boolean;
  build_output: string;
  app_path: string;
  launch_success: boolean;
}

export function registerLifecycleTools(server: McpServer, ctx: ServerContext): void {
  // 1. idb_launch
  server.registerTool("idb_launch", {
    description: "Launch an app on the simulator by bundle ID. Falls back to config bundle_id if not specified.",
    inputSchema: { bundle_id: z.string().optional().describe("App bundle ID (default: from config)") },
  }, async ({ bundle_id }) => {
    const bid = bundle_id || ctx.config.app.bundle_id;
    if (!bid) return { content: [{ type: "text" as const, text: "Error: No bundle_id provided and none in config." }], isError: true };
    await execCommand("idb", ["launch", "--udid", ctx.udid, bid]);
    return { content: [{ type: "text" as const, text: `Launched ${bid}` }] };
  });

  // 2. idb_terminate
  server.registerTool("idb_terminate", {
    description: "Terminate a running app on the simulator.",
    inputSchema: { bundle_id: z.string().optional().describe("App bundle ID (default: from config)") },
  }, async ({ bundle_id }) => {
    const bid = bundle_id || ctx.config.app.bundle_id;
    if (!bid) return { content: [{ type: "text" as const, text: "Error: No bundle_id provided and none in config." }], isError: true };
    try {
      await execCommand("idb", ["terminate", "--udid", ctx.udid, bid]);
    } catch {
      // App may not be running — that's fine
    }
    return { content: [{ type: "text" as const, text: `Terminated ${bid}` }] };
  });

  // 3. idb_install
  server.registerTool("idb_install", {
    description: "Install a .app bundle on the simulator.",
    inputSchema: { app_path: z.string().describe("Path to .app bundle") },
  }, async ({ app_path }) => {
    await execCommand("idb", ["install", "--udid", ctx.udid, app_path], { timeoutMs: 60_000 });
    return { content: [{ type: "text" as const, text: `Installed ${app_path}` }] };
  });

  // 4. build_and_launch
  server.registerTool("build_and_launch", {
    description: "Build the app with the configured build command, find the .app bundle, install it, and launch. Full build-install-launch cycle.",
    inputSchema: { configuration: z.enum(["Debug", "Release"]).optional().describe("Build configuration (default: Debug)") },
  }, async ({ configuration }) => {
    const buildCmd = ctx.config.app.build_command;
    if (!buildCmd) return { content: [{ type: "text" as const, text: "Error: No build_command in config." }], isError: true };

    // Build
    const { stdout: buildOutput } = await execShell(buildCmd, { timeoutMs: 300_000 });

    // Find .app bundle
    const findScript = join(ctx.pluginRoot, "scripts", "find-app-bundle.sh");
    const config = configuration ?? "Debug";
    const { stdout: appPath } = await execCommand("bash", [findScript, "--configuration", config]);
    const trimmedPath = appPath.trim();

    // Install
    await execCommand("idb", ["install", "--udid", ctx.udid, trimmedPath], { timeoutMs: 60_000 });

    // Launch
    const bid = ctx.config.app.bundle_id;
    await execCommand("idb", ["launch", "--udid", ctx.udid, bid]);

    return { content: [{ type: "text" as const, text: `Built, installed (${trimmedPath}), and launched ${bid}` }] };
  });
}
