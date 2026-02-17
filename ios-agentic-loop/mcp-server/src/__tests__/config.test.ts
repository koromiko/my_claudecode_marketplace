import { describe, it, expect, vi, beforeEach } from "vitest";
import { loadConfig, DEFAULT_CONFIG } from "../config.js";
import * as fs from "fs";

vi.mock("fs");

describe("loadConfig", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("returns defaults when no config file exists", async () => {
    vi.mocked(fs.existsSync).mockReturnValue(false);
    const config = await loadConfig();
    expect(config.simulator.device).toBe("iPhone 16 Pro");
    expect(config.idb.action_delay_ms).toBe(500);
  });

  it("deep-merges YAML config over defaults", async () => {
    vi.mocked(fs.existsSync).mockReturnValue(true);
    vi.mocked(fs.readFileSync).mockReturnValue(
      'app:\n  bundle_id: "com.test.app"\nidb:\n  action_delay_ms: 800\n'
    );
    const config = await loadConfig();
    expect(config.app.bundle_id).toBe("com.test.app");
    expect(config.idb.action_delay_ms).toBe(800);
    // defaults preserved for unset fields
    expect(config.simulator.device).toBe("iPhone 16 Pro");
    expect(config.maestro.prefer_id_selectors).toBe(true);
  });

  it("respects AGENTIC_CONFIG_PATH env var", async () => {
    process.env.AGENTIC_CONFIG_PATH = "/custom/path.yaml";
    vi.mocked(fs.existsSync).mockReturnValue(true);
    vi.mocked(fs.readFileSync).mockReturnValue('simulator:\n  device: "iPad Pro"\n');
    const config = await loadConfig();
    expect(fs.readFileSync).toHaveBeenCalledWith("/custom/path.yaml", "utf-8");
    expect(config.simulator.device).toBe("iPad Pro");
    delete process.env.AGENTIC_CONFIG_PATH;
  });
});
