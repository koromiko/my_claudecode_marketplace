/**
 * idb tool definitions for the MCP server.
 * Provides screenshot, accessibility tree, and interaction tools.
 */

// TODO: Phase 2 - Import MCP types
// import { Server } from "@modelcontextprotocol/sdk/server/index.js";
// import { AgenticConfig } from "../config.js";

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

// TODO: Phase 2 - Implement tool registration
// export function registerIdbTools(server: Server, config: AgenticConfig): void {
//   server.setRequestHandler(ListToolsRequestSchema, async () => ({
//     tools: [
//       {
//         name: "idb_screenshot",
//         description: "Capture a screenshot of the current simulator screen",
//         inputSchema: { type: "object", properties: { output_path: { type: "string" } } }
//       },
//       {
//         name: "idb_describe_all",
//         description: "Get the accessibility element tree of the current screen",
//         inputSchema: { type: "object", properties: {} }
//       },
//       {
//         name: "idb_tap",
//         description: "Tap at coordinates on the simulator screen",
//         inputSchema: { type: "object", properties: { x: { type: "number" }, y: { type: "number" } }, required: ["x", "y"] }
//       },
//       {
//         name: "idb_text",
//         description: "Type text into the currently focused field",
//         inputSchema: { type: "object", properties: { text: { type: "string" } }, required: ["text"] }
//       },
//       {
//         name: "idb_swipe",
//         description: "Swipe from (x1,y1) to (x2,y2)",
//         inputSchema: { type: "object", properties: { x1: { type: "number" }, y1: { type: "number" }, x2: { type: "number" }, y2: { type: "number" }, duration: { type: "number" } }, required: ["x1", "y1", "x2", "y2"] }
//       },
//       {
//         name: "observe_screen",
//         description: "Take a screenshot AND get the accessibility tree in one call",
//         inputSchema: { type: "object", properties: {} }
//       }
//     ]
//   }));
// }
