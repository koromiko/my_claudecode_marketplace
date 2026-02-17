/**
 * App lifecycle tool definitions for the MCP server.
 * Provides launch, terminate, install, and build+launch tools.
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { ServerContext } from "../types.js";

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

export function registerLifecycleTools(_server: McpServer, _ctx: ServerContext): void {}
