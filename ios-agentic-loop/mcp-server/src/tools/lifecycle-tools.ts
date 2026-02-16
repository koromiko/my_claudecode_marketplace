/**
 * App lifecycle tool definitions for the MCP server.
 * Provides launch, terminate, install, and build+launch tools.
 */

export interface LaunchParams {
  bundle_id: string;
}

export interface TerminateParams {
  bundle_id: string;
}

export interface InstallParams {
  app_path: string;
}

export interface BuildAndLaunchParams {
  configuration?: "Debug" | "Release";
}

export interface BuildAndLaunchResult {
  build_success: boolean;
  build_output: string;
  app_path: string;
  launch_success: boolean;
}

// TODO: Phase 2 - Implement tool registration
// export function registerLifecycleTools(server: Server, config: AgenticConfig): void {
//   // idb_launch: Launch app by bundle ID
//   // idb_terminate: Terminate running app
//   // idb_install: Install .app bundle on simulator
//   // build_and_launch: Build with project build command, install, and launch
// }
