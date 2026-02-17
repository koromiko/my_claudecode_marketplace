import { describe, it, expect, vi, beforeEach } from "vitest";
import { execCommand, CommandError } from "../../utils/exec-command.js";
import * as childProcess from "child_process";

vi.mock("child_process");

describe("execCommand", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("resolves with stdout on success", async () => {
    vi.mocked(childProcess.execFile).mockImplementation(
      (_cmd, _args, _opts, cb: any) => { cb(null, "output\n", ""); return {} as any; }
    );
    const result = await execCommand("idb", ["screenshot", "/tmp/test.png"]);
    expect(result.stdout).toBe("output\n");
    expect(result.exitCode).toBe(0);
  });

  it("rejects with CommandError on non-zero exit", async () => {
    const err = Object.assign(new Error("fail"), { code: 1 });
    vi.mocked(childProcess.execFile).mockImplementation(
      (_cmd, _args, _opts, cb: any) => { cb(err, "", "error msg"); return {} as any; }
    );
    await expect(execCommand("idb", ["bad"])).rejects.toThrow(CommandError);
  });

  it("rejects with CommandError containing ENOENT for missing binary", async () => {
    const err = Object.assign(new Error("not found"), { code: "ENOENT" });
    vi.mocked(childProcess.execFile).mockImplementation(
      (_cmd, _args, _opts, cb: any) => { cb(err, "", ""); return {} as any; }
    );
    try {
      await execCommand("nonexistent", []);
    } catch (e) {
      expect(e).toBeInstanceOf(CommandError);
      expect((e as CommandError).message).toContain("not found");
    }
  });
});
