import SwiftUI

struct MainTabView: View {
    var body: some View {
        TabView {
            TaskListView()
                .tabItem {
                    Image(systemName: "checklist")
                    Text("Tasks")
                }
                .accessibilityIdentifier("tab_home")

            SettingsView()
                .tabItem {
                    Image(systemName: "gear")
                    Text("Settings")
                }
                .accessibilityIdentifier("tab_settings")
        }
    }
}
