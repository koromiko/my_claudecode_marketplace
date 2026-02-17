/**
 * idb tool definitions for the MCP server.
 * Provides screenshot, accessibility tree, and interaction tools.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { readFileSync, mkdirSync, existsSync } from "fs";
import type { ServerContext } from "../types.js";
import { execCommand } from "../utils/exec-command.js";
import { actionDelay } from "../utils/action-delay.js";

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

export function registerIdbTools(server: McpServer, ctx: ServerContext): void {
  const ensureTmpDir = () => {
    if (!existsSync("/tmp/agentic")) mkdirSync("/tmp/agentic", { recursive: true });
  };

  // 1. idb_screenshot
  server.registerTool("idb_screenshot", {
    description: "Capture a screenshot of the current iOS simulator screen. Returns the image for visual inspection.",
    inputSchema: { output_path: z.string().optional().describe("Custom output path (default: /tmp/agentic/screenshot_<ts>.png)") },
  }, async ({ output_path }) => {
    ensureTmpDir();
    const path = output_path ?? `/tmp/agentic/screenshot_${Date.now()}.png`;
    await execCommand("idb", ["screenshot", "--udid", ctx.udid, path]);
    const data = readFileSync(path).toString("base64");
    return { content: [
      { type: "image" as const, data, mimeType: "image/png" },
      { type: "text" as const, text: `Screenshot saved to ${path}` },
    ]};
  });

  // 2. idb_describe_all
  server.registerTool("idb_describe_all", {
    description: "Get the accessibility element tree of the current screen as JSON. Returns element labels, frames, types, and identifiers.",
    inputSchema: {},
  }, async () => {
    const { stdout } = await execCommand("idb", ["ui", "describe-all", "--udid", ctx.udid, "--format", "json"],
      { timeoutMs: ctx.config.idb.describe_all_timeout_ms });
    return { content: [{ type: "text" as const, text: stdout || "[]" }] };
  });

  // 3. idb_tap
  server.registerTool("idb_tap", {
    description: "Tap at (x, y) coordinates on the simulator screen. Compute center from AXFrame: x = frame.x + width/2, y = frame.y + height/2.",
    inputSchema: {
      x: z.number().describe("X coordinate to tap"),
      y: z.number().describe("Y coordinate to tap"),
    },
  }, async ({ x, y }) => {
    await execCommand("idb", ["ui", "tap", "--udid", ctx.udid, String(x), String(y)]);
    await actionDelay(ctx.config);
    return { content: [{ type: "text" as const, text: `Tapped at (${x}, ${y})` }] };
  });

  // 4. idb_text
  server.registerTool("idb_text", {
    description: "Type text into the currently focused text field. Tap the field first to focus it.",
    inputSchema: { text: z.string().describe("Text to type") },
  }, async ({ text }) => {
    await execCommand("idb", ["ui", "text", "--udid", ctx.udid, text]);
    await actionDelay(ctx.config);
    return { content: [{ type: "text" as const, text: `Typed: "${text}"` }] };
  });

  // 5. idb_swipe
  server.registerTool("idb_swipe", {
    description: "Swipe from (x1,y1) to (x2,y2). Use for scrolling, dismissing, or navigating.",
    inputSchema: {
      x1: z.number().describe("Start X"), y1: z.number().describe("Start Y"),
      x2: z.number().describe("End X"), y2: z.number().describe("End Y"),
      duration: z.number().optional().describe("Swipe duration in seconds (default: 0.3)"),
    },
  }, async ({ x1, y1, x2, y2, duration }) => {
    const d = String(duration ?? 0.3);
    await execCommand("idb", ["ui", "swipe", "--udid", ctx.udid, String(x1), String(y1), String(x2), String(y2), "--duration", d]);
    await actionDelay(ctx.config);
    return { content: [{ type: "text" as const, text: `Swiped (${x1},${y1}) → (${x2},${y2})` }] };
  });

  // 6. observe_screen — dual-channel ORAV observation
  server.registerTool("observe_screen", {
    description: "Take a screenshot AND get the accessibility tree in one call. Primary ORAV loop observation tool.",
    inputSchema: {},
  }, async () => {
    ensureTmpDir();
    const path = `/tmp/agentic/observe_${Date.now()}.png`;
    const [, descResult] = await Promise.all([
      execCommand("idb", ["screenshot", "--udid", ctx.udid, path]),
      execCommand("idb", ["ui", "describe-all", "--udid", ctx.udid, "--format", "json"],
        { timeoutMs: ctx.config.idb.describe_all_timeout_ms }),
    ]);
    const data = readFileSync(path).toString("base64");
    return { content: [
      { type: "image" as const, data, mimeType: "image/png" },
      { type: "text" as const, text: descResult.stdout || "[]" },
    ]};
  });
}
