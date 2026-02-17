import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @State private var showClearConfirmation = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Preferences") {
                    Toggle("Dark Mode", isOn: $appState.isDarkMode)
                        .accessibilityIdentifier("settings_toggle_dark_mode")

                    Toggle("Notifications", isOn: $appState.notificationsEnabled)
                        .accessibilityIdentifier("settings_toggle_notifications")
                }

                Section("Data") {
                    Button("Clear All Data", role: .destructive) {
                        showClearConfirmation = true
                    }
                    .accessibilityIdentifier("settings_button_clear")
                }

                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("1.0.0")
                            .foregroundStyle(.secondary)
                    }
                    .accessibilityIdentifier("settings_label_version")

                    HStack {
                        Text("Tasks")
                        Spacer()
                        Text("\(appState.tasks.count)")
                            .foregroundStyle(.secondary)
                    }
                }

                Section {
                    Button("Sign Out") {
                        appState.logout()
                    }
                    .frame(maxWidth: .infinity)
                    .foregroundStyle(.red)
                    .accessibilityIdentifier("settings_button_logout")
                }
            }
            .navigationTitle("Settings")
            .confirmationDialog("Clear All Data?", isPresented: $showClearConfirmation, titleVisibility: .visible) {
                Button("Clear Everything", role: .destructive) {
                    appState.clearAllData()
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This will remove all tasks and reset settings. This cannot be undone.")
            }
        }
    }
}
