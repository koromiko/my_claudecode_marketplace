import type { MaestroRunResult, MaestroFailure } from "../tools/maestro-tools.js";

export function parseMaestroOutput(stdout: string): MaestroRunResult {
  const passedMatch = stdout.match(/Passed:\s*(\d+)/);
  const failedMatch = stdout.match(/Failed:\s*(\d+)/);
  const passed = passedMatch ? parseInt(passedMatch[1], 10) : 0;
  const failed = failedMatch ? parseInt(failedMatch[1], 10) : 0;

  const failures: MaestroFailure[] = [];
  const failRegex = /❌\s+(.+?)\s+-\s+Step\s+(\d+):\s+(.+)/g;
  let match;
  while ((match = failRegex.exec(stdout)) !== null) {
    failures.push({ flow_name: match[1].trim(), step_number: parseInt(match[2], 10), error: match[3].trim() });
  }

  return {
    success: failed === 0,
    total_flows: passed + failed,
    passed,
    failed,
    failures,
  };
}
