import { describe, it, expect, vi } from "vitest";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerMaestroTools } from "../../tools/maestro-tools.js";
import type { ServerContext } from "../../types.js";

vi.mock("../../utils/exec-command.js");
vi.mock("fs");

const ctx: ServerContext = {
  config: {
    simulator: { device: "iPhone 16 Pro", runtime: "iOS 18.2", udid: "TEST-UDID" },
    app: { bundle_id: "com.test.app", extension_bundle_ids: [], build_command: "", app_group: "" },
    idb: { action_delay_ms: 100, describe_all_timeout_ms: 5000 },
    loop: { max_steps_per_goal: 30, max_retries_per_action: 3, verify_timeout_ms: 2000 },
    maestro: { output_dir: "tests/maestro/flows", prefer_id_selectors: true, include_ai_assertions: true },
    artifacts: { results_dir: "tests/agentic/results", keep_last_n_runs: 10 },
  },
  udid: "TEST-UDID",
  pluginRoot: "/plugin",
};

describe("maestro tools registration", () => {
  it("registers 2 tools on the server", () => {
    const server = new McpServer({ name: "test", version: "1.0.0" });
    const spy = vi.spyOn(server, "registerTool" as any);
    registerMaestroTools(server, ctx);
    expect(spy).toHaveBeenCalledTimes(2);
  });
});
