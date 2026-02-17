import { describe, it, expect } from "vitest";
import { parseMaestroOutput } from "../../utils/maestro-parser.js";

describe("parseMaestroOutput", () => {
  it("parses successful run output", () => {
    const output = `
Running tests...

 \u2705  flows/smoke/app_launch.yaml
 \u2705  flows/smoke/tab_nav.yaml

==== Test results ====
Passed: 2, Failed: 0
`;
    const result = parseMaestroOutput(output);
    expect(result.success).toBe(true);
    expect(result.passed).toBe(2);
    expect(result.failed).toBe(0);
    expect(result.failures).toHaveLength(0);
  });

  it("parses failed run output", () => {
    const output = `
Running tests...

 \u2705  flows/smoke/app_launch.yaml
 \u274C  flows/auth/login.yaml - Step 4: tapOn failed - Element not found

==== Test results ====
Passed: 1, Failed: 1
`;
    const result = parseMaestroOutput(output);
    expect(result.success).toBe(false);
    expect(result.passed).toBe(1);
    expect(result.failed).toBe(1);
    expect(result.failures).toHaveLength(1);
    expect(result.failures[0].flow_name).toContain("login");
  });
});
