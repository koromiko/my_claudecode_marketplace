/**
 * Maestro tool definitions for the MCP server.
 * Provides test execution and flow export tools.
 */

export interface MaestroRunParams {
  flow_path: string;
  continuous?: boolean;
  include_tags?: string[];
}

export interface MaestroRunResult {
  success: boolean;
  total_flows: number;
  passed: number;
  failed: number;
  failures: MaestroFailure[];
}

export interface MaestroFailure {
  flow_name: string;
  step_number: number;
  error: string;
}

export interface ActionLogEntry {
  step: number;
  action: string;
  x?: number;
  y?: number;
  text?: string;
  label?: string;
  type?: string;
  a11y_id?: string;
  verified: boolean;
}

export interface ExportFlowParams {
  action_log: ActionLogEntry[];
  flow_name: string;
  output_dir?: string;
}

export interface ExportFlowResult {
  flow_path: string;
  steps_count: number;
}

// TODO: Phase 2 - Implement tool registration
// export function registerMaestroTools(server: Server, config: AgenticConfig): void {
//   // maestro_run: Run Maestro test flows
//   // maestro_export_flow: Convert action log to Maestro YAML
// }
