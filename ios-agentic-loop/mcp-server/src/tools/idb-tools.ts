/**
 * idb tool definitions for the MCP server.
 * Provides screenshot, accessibility tree, and interaction tools.
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { ServerContext } from "../types.js";

export interface ScreenshotParams {
  output_path?: string;
}

export interface DescribeAllResult {
  elements: AccessibilityElement[];
}

export interface AccessibilityElement {
  AXLabel: string | null;
  AXFrame: string;
  AXType: string;
  AXEnabled: boolean;
  AXValue: string | null;
  AXUniqueId: string | null;
}

export interface TapParams {
  x: number;
  y: number;
}

export interface TextParams {
  text: string;
}

export interface SwipeParams {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  duration?: number;
}

export interface ObserveScreenResult {
  screenshot_path: string;
  elements: AccessibilityElement[];
}

export function registerIdbTools(_server: McpServer, _ctx: ServerContext): void {}
