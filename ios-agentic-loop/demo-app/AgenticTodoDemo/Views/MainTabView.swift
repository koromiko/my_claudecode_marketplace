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

            ExploreView()
                .tabItem {
                    Image(systemName: "mappin.and.ellipse")
                    Text("Explore")
                }
                .accessibilityIdentifier("tab_explore")

            SettingsView()
                .tabItem {
                    Image(systemName: "gear")
                    Text("Settings")
                }
                .accessibilityIdentifier("tab_settings")
        }
    }
}
