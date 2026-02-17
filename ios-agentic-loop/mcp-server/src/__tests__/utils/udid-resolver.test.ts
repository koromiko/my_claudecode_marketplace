import { describe, it, expect, vi, beforeEach } from "vitest";
import { resolveUdid, _resetCache } from "../../utils/udid-resolver.js";
import * as execMod from "../../utils/exec-command.js";

vi.mock("../../utils/exec-command.js");

const SIMCTL_OUTPUT = JSON.stringify({
  devices: {
    "com.apple.CoreSimulator.SimRuntime.iOS-18-2": [
      { udid: "AAAA-1111", name: "iPhone 16 Pro", state: "Booted", isAvailable: true },
      { udid: "BBBB-2222", name: "iPhone 15", state: "Shutdown", isAvailable: true }
    ],
    "com.apple.CoreSimulator.SimRuntime.iOS-17-0": [
      { udid: "CCCC-3333", name: "iPhone 15", state: "Booted", isAvailable: true }
    ]
  }
});

describe("resolveUdid", () => {
  beforeEach(() => { vi.restoreAllMocks(); _resetCache(); });

  it("returns config udid if not 'auto'", async () => {
    const udid = await resolveUdid({ simulator: { device: "", runtime: "", udid: "EXPLICIT-UDID" } } as any);
    expect(udid).toBe("EXPLICIT-UDID");
  });

  it("auto-resolves preferring device matching config name", async () => {
    vi.mocked(execMod.execCommand).mockResolvedValue({ stdout: SIMCTL_OUTPUT, stderr: "", exitCode: 0 });
    const udid = await resolveUdid({ simulator: { device: "iPhone 16 Pro", runtime: "", udid: "auto" } } as any);
    expect(udid).toBe("AAAA-1111");
  });

  it("falls back to first booted device if no name match", async () => {
    vi.mocked(execMod.execCommand).mockResolvedValue({ stdout: SIMCTL_OUTPUT, stderr: "", exitCode: 0 });
    const udid = await resolveUdid({ simulator: { device: "iPad Air", runtime: "", udid: "auto" } } as any);
    expect(udid).toBe("AAAA-1111");
  });

  it("throws if no booted simulators", async () => {
    const empty = JSON.stringify({ devices: { "runtime": [{ udid: "X", name: "Y", state: "Shutdown" }] } });
    vi.mocked(execMod.execCommand).mockResolvedValue({ stdout: empty, stderr: "", exitCode: 0 });
    await expect(resolveUdid({ simulator: { device: "", runtime: "", udid: "auto" } } as any))
      .rejects.toThrow(/no booted/i);
  });
});
