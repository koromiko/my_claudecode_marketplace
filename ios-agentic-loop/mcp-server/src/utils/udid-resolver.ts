import type { AgenticConfig } from "../config.js";
import { execCommand } from "./exec-command.js";

let cachedUdid: string | null = null;

export function _resetCache(): void { cachedUdid = null; }

export async function resolveUdid(config: AgenticConfig): Promise<string> {
  if (config.simulator.udid !== "auto") return config.simulator.udid;
  if (cachedUdid) return cachedUdid;

  const { stdout } = await execCommand("xcrun", ["simctl", "list", "devices", "booted", "-j"]);
  const data = JSON.parse(stdout);
  const booted: Array<{ udid: string; name: string }> = [];

  for (const devices of Object.values(data.devices) as any[][]) {
    for (const d of devices) {
      if (d.state === "Booted") booted.push({ udid: d.udid, name: d.name });
    }
  }

  if (booted.length === 0) {
    throw new Error("No booted simulators found. Use boot_simulator tool or: xcrun simctl boot 'iPhone 16 Pro'");
  }

  const preferred = booted.find(d => d.name === config.simulator.device);
  cachedUdid = preferred ? preferred.udid : booted[0].udid;
  return cachedUdid;
}
