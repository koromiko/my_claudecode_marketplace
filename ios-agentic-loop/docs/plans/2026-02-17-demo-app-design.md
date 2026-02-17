# AgenticTodo Demo App Design

## Purpose

A self-contained SwiftUI demo app inside the plugin repo that exercises every major plugin component: agents (ORAV loop), commands, skills, hooks, scripts, and templates. Anyone cloning the plugin can build and run the demo to verify the full agentic iOS testing workflow.

## Decisions

- **Location:** `ios-agentic-loop/demo-app/`
- **Build system:** XcodeGen (`project.yml`) — no `.xcodeproj` checked in
- **App theme:** Task/Todo manager — covers text input, taps, toggles, swipes, navigation, pickers
- **Framework:** SwiftUI, iOS 17+
- **Persistence:** None (in-memory only) — deterministic state for testing
- **Bundle ID:** `com.agentic-loop.demo`
- **Scheme:** `AgenticTodoDemo`

## Screens

| Screen | Elements | Plugin Features Exercised |
|--------|----------|--------------------------|
| Login | Email field, password field, login button, forgot password link | `idb ui text`, tap, keyboard dismiss |
| Task List (Home tab) | Task list with checkboxes, add button, swipe-to-delete | Tap, swipe, list scrolling, dynamic elements |
| Task Detail | Title, description, due date, priority picker, save | Text fields, picker, navigation push/pop |
| Settings (tab) | Dark mode toggle, notifications toggle, clear data, version label | Toggle, destructive action, static assertions |
| Add Task (modal) | Title field, description, priority picker, save/cancel | Sheet presentation, form input, dismiss |

## Accessibility Identifiers

Following the plugin's `{scope}_{type}_{name}` convention:

```
Login:      login_field_email, login_field_password, login_button_submit, login_button_forgot
Home:       home_list_tasks, home_button_add, home_cell_task_{id}
Detail:     detail_field_title, detail_field_description, detail_picker_priority, detail_button_save
Settings:   settings_toggle_dark_mode, settings_toggle_notifications, settings_button_clear, settings_label_version
Add Task:   modal_field_title, modal_field_description, modal_picker_priority, modal_button_save, modal_button_cancel
Navigation: tab_home, tab_settings, nav_button_back
```

## File Structure

```
demo-app/
├── project.yml
├── AgenticTodoDemo/
│   ├── App.swift
│   ├── Models/
│   │   └── Task.swift
│   ├── Views/
│   │   ├── LoginView.swift
│   │   ├── MainTabView.swift
│   │   ├── TaskListView.swift
│   │   ├── TaskDetailView.swift
│   │   ├── AddTaskView.swift
│   │   └── SettingsView.swift
│   ├── ViewModels/
│   │   └── AppState.swift
│   └── Assets.xcassets/
│       └── (AppIcon, AccentColor)
├── agentic-loop.config.yaml
└── tests/
    └── maestro/
        └── flows/
            └── smoke/
                └── app_launch.yaml
```

## Data Model

```swift
struct TodoTask: Identifiable {
    let id: UUID
    var title: String
    var description: String
    var priority: Priority       // .low, .medium, .high
    var isDone: Bool
    var dueDate: Date?
}

enum Priority: String, CaseIterable {
    case low, medium, high
}
```

## AppState

```swift
class AppState: ObservableObject {
    @Published var isLoggedIn = false
    @Published var tasks: [TodoTask] = TodoTask.sampleData
    @Published var isDarkMode = false
    @Published var notificationsEnabled = true
}
```

Seeded with 3-5 sample tasks on launch so the list is never empty for exploration.

## Verification Guide

Step-by-step guide included alongside the demo app covering:

1. **Build & install** — `xcodegen generate && xcodebuild ... && xcrun simctl install`
2. **Plugin setup** — pre-configured `agentic-loop.config.yaml` ships with the demo
3. **ORAV exploration** — invoke `ui-explorer` agent for autonomous app exploration
4. **Goal-directed test** — test login flow with specific credentials
5. **Maestro export** — export action log to Maestro YAML via `/export-maestro-flow`
6. **Regression run** — run exported + smoke flows via `/run-maestro`
7. **Accessibility audit** — run `/audit-accessibility` to verify identifier coverage
8. **Hook verification** — edit a View.swift to trigger the PostToolUse accessibility hook

This exercises every plugin component: agents, commands, skills, scripts, hooks, templates.
