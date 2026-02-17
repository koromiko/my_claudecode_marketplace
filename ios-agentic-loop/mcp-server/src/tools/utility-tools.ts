import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { join } from "path";
import type { ServerContext } from "../types.js";
import { execCommand } from "../utils/exec-command.js";

export function registerUtilityTools(server: McpServer, ctx: ServerContext): void {
  // 1. idb_key_press
  server.registerTool("idb_key_press", {
    description: "Press a key on the simulator (escape, return, home, backspace). Useful for dismissing keyboard or confirming input.",
    inputSchema: { key: z.string().describe("Key name: escape, return, home, backspace") },
  }, async ({ key }) => {
    await execCommand("idb", ["ui", "key", "--udid", ctx.udid, "1", key]);
    return { content: [{ type: "text" as const, text: `Pressed key: ${key}` }] };
  });

  // 2. reset_test_state
  server.registerTool("reset_test_state", {
    description: "Reset app state on simulator (terminate, clear UserDefaults, optionally reset keychain). Provides a clean slate for testing.",
    inputSchema: {
      bundle_id: z.string().optional().describe("App bundle ID (default: from config)"),
      reset_keychain: z.boolean().optional().describe("Also reset the simulator keychain"),
    },
  }, async ({ bundle_id, reset_keychain }) => {
    const bid = bundle_id || ctx.config.app.bundle_id;
    if (!bid) return { content: [{ type: "text" as const, text: "Error: No bundle_id." }], isError: true };

    const script = join(ctx.pluginRoot, "scripts", "reset-test-state.sh");
    const args = [script, bid];
    if (ctx.config.app.app_group) args.push("--app-group", ctx.config.app.app_group);
    if (reset_keychain) args.push("--keychain");

    const { stdout } = await execCommand("bash", args);
    return { content: [{ type: "text" as const, text: stdout }] };
  });

  // 3. boot_simulator
  server.registerTool("boot_simulator", {
    description: "Boot an iOS simulator by device name. Waits for boot to complete.",
    inputSchema: {
      device_name: z.string().optional().describe("Simulator name (default: from config)"),
      runtime: z.string().optional().describe("iOS runtime version"),
    },
  }, async ({ device_name, runtime }) => {
    const name = device_name || ctx.config.simulator.device;
    const script = join(ctx.pluginRoot, "scripts", "boot-simulator.sh");
    const args = [script, name];
    if (runtime) args.push("--runtime", runtime);

    const { stdout } = await execCommand("bash", args, { timeoutMs: 60_000 });
    return { content: [{ type: "text" as const, text: stdout }] };
  });

  // 4. check_prerequisites
  server.registerTool("check_prerequisites", {
    description: "Check that all prerequisites are installed (Xcode, idb, Maestro, booted simulator). Returns pass/fail for each.",
    inputSchema: {},
  }, async () => {
    const script = join(ctx.pluginRoot, "scripts", "check-prerequisites.sh");
    try {
      const { stdout } = await execCommand("bash", [script], { timeoutMs: 30_000 });
      return { content: [{ type: "text" as const, text: stdout }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: err.stdout || err.message }] };
    }
  });
}
