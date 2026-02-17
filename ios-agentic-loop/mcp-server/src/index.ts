import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { loadConfig } from "./config.js";
import { resolveUdid } from "./utils/udid-resolver.js";
import { registerIdbTools } from "./tools/idb-tools.js";
import { registerLifecycleTools } from "./tools/lifecycle-tools.js";
import { registerMaestroTools } from "./tools/maestro-tools.js";
import { registerUtilityTools } from "./tools/utility-tools.js";
import type { ServerContext } from "./types.js";

async function main(): Promise<void> {
  const config = await loadConfig();
  const udid = await resolveUdid(config);
  const pluginRoot = process.env.CLAUDE_PLUGIN_ROOT || process.cwd();

  const ctx: ServerContext = { config, udid, pluginRoot };

  const server = new McpServer({ name: "ios-agentic-loop", version: "1.0.0" });

  registerIdbTools(server, ctx);
  registerLifecycleTools(server, ctx);
  registerMaestroTools(server, ctx);
  registerUtilityTools(server, ctx);

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("MCP server failed to start:", err.message);
  process.exit(1);
});
