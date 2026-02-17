import { execFile, exec } from "child_process";

export class CommandError extends Error {
  constructor(
    public readonly command: string,
    public readonly exitCode: number | string,
    public readonly stderr: string,
    public readonly stdout: string
  ) {
    const hint = exitCode === "ENOENT"
      ? `Command not found: "${command}". Is it installed and on PATH?`
      : `Command failed: "${command}" (exit ${exitCode}): ${stderr.slice(0, 200)}`;
    super(hint);
    this.name = "CommandError";
  }
}

export interface ExecResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

export function execCommand(
  command: string,
  args: string[],
  options?: { timeoutMs?: number; cwd?: string }
): Promise<ExecResult> {
  const timeoutMs = options?.timeoutMs ?? 30_000;
  return new Promise((resolve, reject) => {
    execFile(command, args, { timeout: timeoutMs, cwd: options?.cwd, maxBuffer: 10 * 1024 * 1024 },
      (error, stdout, stderr) => {
        if (error) {
          const code = (error as any).code ?? (error as any).exitCode ?? 1;
          reject(new CommandError(command, code, stderr ?? "", stdout ?? ""));
          return;
        }
        resolve({ stdout: stdout ?? "", stderr: stderr ?? "", exitCode: 0 });
      }
    );
  });
}

export function execShell(
  command: string,
  options?: { timeoutMs?: number; cwd?: string }
): Promise<ExecResult> {
  const timeoutMs = options?.timeoutMs ?? 30_000;
  return new Promise((resolve, reject) => {
    exec(command, { timeout: timeoutMs, cwd: options?.cwd, maxBuffer: 10 * 1024 * 1024 },
      (error, stdout, stderr) => {
        if (error) {
          const code = (error as any).code ?? (error as any).exitCode ?? 1;
          reject(new CommandError(command, code, stderr ?? "", stdout ?? ""));
          return;
        }
        resolve({ stdout: stdout ?? "", stderr: stderr ?? "", exitCode: 0 });
      }
    );
  });
}
