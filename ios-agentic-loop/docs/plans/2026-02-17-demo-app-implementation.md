# AgenticTodo Demo App Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a SwiftUI todo app at `demo-app/` that exercises every ios-agentic-loop plugin component — agents, commands, skills, hooks, scripts, templates.

**Architecture:** SwiftUI single-target app using XcodeGen. In-memory data only (no persistence). 4 screens + 1 modal sheet, all with accessibility identifiers following `{scope}_{type}_{name}` convention. Pre-configured `agentic-loop.config.yaml` and Maestro smoke test included.

**Tech Stack:** Swift 5.9+, SwiftUI, iOS 17+, XcodeGen

---

### Task 1: Scaffold directory structure

**Files:**
- Create: `demo-app/AgenticTodoDemo/Models/` (directory)
- Create: `demo-app/AgenticTodoDemo/Views/` (directory)
- Create: `demo-app/AgenticTodoDemo/ViewModels/` (directory)
- Create: `demo-app/AgenticTodoDemo/Assets.xcassets/AccentColor.colorset/Contents.json`
- Create: `demo-app/AgenticTodoDemo/Assets.xcassets/AppIcon.appiconset/Contents.json`
- Create: `demo-app/AgenticTodoDemo/Assets.xcassets/Contents.json`
- Create: `demo-app/tests/maestro/flows/smoke/` (directory)
- Create: `demo-app/.gitignore`

All paths are relative to `ios-agentic-loop/`.

**Step 1: Create directories**

```bash
cd ios-agentic-loop
mkdir -p demo-app/AgenticTodoDemo/Models
mkdir -p demo-app/AgenticTodoDemo/Views
mkdir -p demo-app/AgenticTodoDemo/ViewModels
mkdir -p demo-app/AgenticTodoDemo/Assets.xcassets/AccentColor.colorset
mkdir -p demo-app/AgenticTodoDemo/Assets.xcassets/AppIcon.appiconset
mkdir -p demo-app/tests/maestro/flows/smoke
mkdir -p demo-app/tests/agentic/scenarios
mkdir -p demo-app/tests/agentic/results
```

**Step 2: Create asset catalog files**

Write `demo-app/AgenticTodoDemo/Assets.xcassets/Contents.json`:
```json
{
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
```

Write `demo-app/AgenticTodoDemo/Assets.xcassets/AccentColor.colorset/Contents.json`:
```json
{
  "colors" : [
    {
      "idiom" : "universal"
    }
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
```

Write `demo-app/AgenticTodoDemo/Assets.xcassets/AppIcon.appiconset/Contents.json`:
```json
{
  "images" : [
    {
      "idiom" : "universal",
      "platform" : "ios",
      "size" : "1024x1024"
    }
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
```

**Step 3: Create .gitignore**

Write `demo-app/.gitignore`:
```
# XcodeGen output
*.xcodeproj

# Xcode
build/
DerivedData/
*.xcworkspace

# Test results
tests/agentic/results/
```

**Step 4: Commit**

```bash
git add demo-app/
git commit -m "scaffold: create demo-app directory structure and asset catalogs"
```

---

### Task 2: Create project.yml (XcodeGen)

**Files:**
- Create: `demo-app/project.yml`

**Step 1: Write project.yml**

Write `demo-app/project.yml`:
```yaml
name: AgenticTodoDemo
options:
  bundleIdPrefix: com.agentic-loop
  deploymentTarget:
    iOS: "17.0"
  xcodeVersion: "16.0"

targets:
  AgenticTodoDemo:
    type: application
    platform: iOS
    sources:
      - AgenticTodoDemo
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: com.agentic-loop.demo
        INFOPLIST_VALUES: >-
          CFBundleDisplayName=AgenticTodo
          CFBundleName=AgenticTodoDemo
          CFBundleShortVersionString=1.0
          CFBundleVersion=1
          UILaunchScreen={}
        SWIFT_VERSION: "5.9"
        DEVELOPMENT_TEAM: ""
        CODE_SIGN_IDENTITY: "-"
        CODE_SIGNING_ALLOWED: "NO"
```

**Step 2: Verify XcodeGen is installed**

```bash
which xcodegen || echo "INSTALL: brew install xcodegen"
```

Expected: path to xcodegen binary (e.g., `/opt/homebrew/bin/xcodegen`)

**Step 3: Commit**

```bash
git add demo-app/project.yml
git commit -m "build: add XcodeGen project.yml for demo app"
```

---

### Task 3: Create data model

**Files:**
- Create: `demo-app/AgenticTodoDemo/Models/Task.swift`

**Step 1: Write Task.swift**

Write `demo-app/AgenticTodoDemo/Models/Task.swift`:
```swift
import Foundation

enum Priority: String, CaseIterable, Identifiable {
    case low, medium, high

    var id: String { rawValue }

    var label: String {
        rawValue.capitalized
    }
}

struct TodoTask: Identifiable {
    let id: UUID
    var title: String
    var description: String
    var priority: Priority
    var isDone: Bool
    var dueDate: Date?

    init(
        id: UUID = UUID(),
        title: String,
        description: String = "",
        priority: Priority = .medium,
        isDone: Bool = false,
        dueDate: Date? = nil
    ) {
        self.id = id
        self.title = title
        self.description = description
        self.priority = priority
        self.isDone = isDone
        self.dueDate = dueDate
    }
}

extension TodoTask {
    static let sampleData: [TodoTask] = [
        TodoTask(
            title: "Buy groceries",
            description: "Milk, eggs, bread, and coffee",
            priority: .high,
            dueDate: Calendar.current.date(byAdding: .day, value: 1, to: .now)
        ),
        TodoTask(
            title: "Review pull request",
            description: "Check the new authentication module",
            priority: .medium
        ),
        TodoTask(
            title: "Update documentation",
            description: "Add setup instructions for the demo app",
            priority: .low,
            dueDate: Calendar.current.date(byAdding: .day, value: 3, to: .now)
        ),
        TodoTask(
            title: "Fix login animation",
            description: "The transition is choppy on older devices",
            priority: .medium,
            isDone: true
        ),
    ]
}
```

**Step 2: Commit**

```bash
git add demo-app/AgenticTodoDemo/Models/Task.swift
git commit -m "feat: add TodoTask model with sample data"
```

---

### Task 4: Create AppState view model

**Files:**
- Create: `demo-app/AgenticTodoDemo/ViewModels/AppState.swift`

**Step 1: Write AppState.swift**

Write `demo-app/AgenticTodoDemo/ViewModels/AppState.swift`:
```swift
import SwiftUI

@MainActor
class AppState: ObservableObject {
    @Published var isLoggedIn = false
    @Published var tasks: [TodoTask] = TodoTask.sampleData
    @Published var isDarkMode = false
    @Published var notificationsEnabled = true

    func login(email: String, password: String) {
        // Accept any non-empty credentials for demo purposes
        if !email.isEmpty && !password.isEmpty {
            isLoggedIn = true
        }
    }

    func logout() {
        isLoggedIn = false
    }

    func addTask(_ task: TodoTask) {
        tasks.append(task)
    }

    func deleteTask(at offsets: IndexSet) {
        tasks.remove(atOffsets: offsets)
    }

    func toggleTask(_ task: TodoTask) {
        if let index = tasks.firstIndex(where: { $0.id == task.id }) {
            tasks[index].isDone.toggle()
        }
    }

    func updateTask(_ task: TodoTask) {
        if let index = tasks.firstIndex(where: { $0.id == task.id }) {
            tasks[index] = task
        }
    }

    func clearAllData() {
        tasks = []
        isDarkMode = false
        notificationsEnabled = true
    }
}
```

**Step 2: Commit**

```bash
git add demo-app/AgenticTodoDemo/ViewModels/AppState.swift
git commit -m "feat: add AppState view model with in-memory task management"
```

---

### Task 5: Create LoginView

**Files:**
- Create: `demo-app/AgenticTodoDemo/Views/LoginView.swift`

**Step 1: Write LoginView.swift**

Write `demo-app/AgenticTodoDemo/Views/LoginView.swift`:
```swift
import SwiftUI

struct LoginView: View {
    @EnvironmentObject var appState: AppState
    @State private var email = ""
    @State private var password = ""
    @State private var showForgotAlert = false

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Text("AgenticTodo")
                .font(.largeTitle.bold())

            Text("Sign in to continue")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            VStack(spacing: 16) {
                TextField("Email", text: $email)
                    .textContentType(.emailAddress)
                    .keyboardType(.emailAddress)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .textFieldStyle(.roundedBorder)
                    .accessibilityIdentifier("login_field_email")

                SecureField("Password", text: $password)
                    .textContentType(.password)
                    .textFieldStyle(.roundedBorder)
                    .accessibilityIdentifier("login_field_password")
            }
            .padding(.horizontal)

            Button {
                appState.login(email: email, password: password)
            } label: {
                Text("Sign In")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
            }
            .buttonStyle(.borderedProminent)
            .padding(.horizontal)
            .accessibilityIdentifier("login_button_submit")

            Button("Forgot Password?") {
                showForgotAlert = true
            }
            .font(.footnote)
            .accessibilityIdentifier("login_button_forgot")

            Spacer()
            Spacer()
        }
        .alert("Reset Password", isPresented: $showForgotAlert) {
            Button("OK", role: .cancel) {}
        } message: {
            Text("Check your email for a password reset link.")
        }
    }
}
```

**Step 2: Commit**

```bash
git add demo-app/AgenticTodoDemo/Views/LoginView.swift
git commit -m "feat: add LoginView with email/password fields and accessibility IDs"
```

---

### Task 6: Create TaskListView

**Files:**
- Create: `demo-app/AgenticTodoDemo/Views/TaskListView.swift`

**Step 1: Write TaskListView.swift**

Write `demo-app/AgenticTodoDemo/Views/TaskListView.swift`:
```swift
import SwiftUI

struct TaskListView: View {
    @EnvironmentObject var appState: AppState
    @State private var showAddTask = false

    var body: some View {
        NavigationStack {
            List {
                ForEach(appState.tasks) { task in
                    NavigationLink(destination: TaskDetailView(task: task)) {
                        TaskRow(task: task)
                    }
                    .accessibilityIdentifier("home_cell_task_\(task.id.uuidString.prefix(8))")
                }
                .onDelete(perform: appState.deleteTask)
            }
            .accessibilityIdentifier("home_list_tasks")
            .navigationTitle("Tasks")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showAddTask = true
                    } label: {
                        Image(systemName: "plus")
                    }
                    .accessibilityIdentifier("home_button_add")
                }
            }
            .sheet(isPresented: $showAddTask) {
                AddTaskView()
            }
        }
    }
}

struct TaskRow: View {
    @EnvironmentObject var appState: AppState
    let task: TodoTask

    var body: some View {
        HStack(spacing: 12) {
            Button {
                appState.toggleTask(task)
            } label: {
                Image(systemName: task.isDone ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(task.isDone ? .green : .secondary)
                    .font(.title3)
            }
            .buttonStyle(.plain)

            VStack(alignment: .leading, spacing: 4) {
                Text(task.title)
                    .strikethrough(task.isDone)
                    .foregroundStyle(task.isDone ? .secondary : .primary)

                if !task.description.isEmpty {
                    Text(task.description)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }

            Spacer()

            PriorityBadge(priority: task.priority)
        }
        .contentShape(Rectangle())
    }
}

struct PriorityBadge: View {
    let priority: Priority

    var color: Color {
        switch priority {
        case .low: .blue
        case .medium: .orange
        case .high: .red
        }
    }

    var body: some View {
        Text(priority.label)
            .font(.caption2.bold())
            .padding(.horizontal, 8)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}
```

**Step 2: Commit**

```bash
git add demo-app/AgenticTodoDemo/Views/TaskListView.swift
git commit -m "feat: add TaskListView with list, swipe-to-delete, and navigation"
```

---

### Task 7: Create TaskDetailView

**Files:**
- Create: `demo-app/AgenticTodoDemo/Views/TaskDetailView.swift`

**Step 1: Write TaskDetailView.swift**

Write `demo-app/AgenticTodoDemo/Views/TaskDetailView.swift`:
```swift
import SwiftUI

struct TaskDetailView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) var dismiss
    @State var task: TodoTask

    var body: some View {
        Form {
            Section("Title") {
                TextField("Task title", text: $task.title)
                    .accessibilityIdentifier("detail_field_title")
            }

            Section("Description") {
                TextField("Description", text: $task.description, axis: .vertical)
                    .lineLimit(3...6)
                    .accessibilityIdentifier("detail_field_description")
            }

            Section("Priority") {
                Picker("Priority", selection: $task.priority) {
                    ForEach(Priority.allCases) { priority in
                        Text(priority.label).tag(priority)
                    }
                }
                .pickerStyle(.segmented)
                .accessibilityIdentifier("detail_picker_priority")
            }

            Section("Due Date") {
                DatePicker(
                    "Due date",
                    selection: Binding(
                        get: { task.dueDate ?? .now },
                        set: { task.dueDate = $0 }
                    ),
                    displayedComponents: .date
                )
                .accessibilityIdentifier("detail_picker_date")
            }

            Section {
                Button("Save") {
                    appState.updateTask(task)
                    dismiss()
                }
                .frame(maxWidth: .infinity)
                .accessibilityIdentifier("detail_button_save")
            }
        }
        .navigationTitle("Task Detail")
    }
}
```

**Step 2: Commit**

```bash
git add demo-app/AgenticTodoDemo/Views/TaskDetailView.swift
git commit -m "feat: add TaskDetailView with editable fields and priority picker"
```

---

### Task 8: Create AddTaskView

**Files:**
- Create: `demo-app/AgenticTodoDemo/Views/AddTaskView.swift`

**Step 1: Write AddTaskView.swift**

Write `demo-app/AgenticTodoDemo/Views/AddTaskView.swift`:
```swift
import SwiftUI

struct AddTaskView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) var dismiss
    @State private var title = ""
    @State private var description = ""
    @State private var priority: Priority = .medium

    var body: some View {
        NavigationStack {
            Form {
                Section("Title") {
                    TextField("What needs to be done?", text: $title)
                        .accessibilityIdentifier("modal_field_title")
                }

                Section("Description") {
                    TextField("Details (optional)", text: $description, axis: .vertical)
                        .lineLimit(3...6)
                        .accessibilityIdentifier("modal_field_description")
                }

                Section("Priority") {
                    Picker("Priority", selection: $priority) {
                        ForEach(Priority.allCases) { priority in
                            Text(priority.label).tag(priority)
                        }
                    }
                    .pickerStyle(.segmented)
                    .accessibilityIdentifier("modal_picker_priority")
                }
            }
            .navigationTitle("New Task")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .accessibilityIdentifier("modal_button_cancel")
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        let task = TodoTask(
                            title: title,
                            description: description,
                            priority: priority
                        )
                        appState.addTask(task)
                        dismiss()
                    }
                    .disabled(title.isEmpty)
                    .accessibilityIdentifier("modal_button_save")
                }
            }
        }
    }
}
```

**Step 2: Commit**

```bash
git add demo-app/AgenticTodoDemo/Views/AddTaskView.swift
git commit -m "feat: add AddTaskView modal with form fields and save/cancel"
```

---

### Task 9: Create SettingsView

**Files:**
- Create: `demo-app/AgenticTodoDemo/Views/SettingsView.swift`

**Step 1: Write SettingsView.swift**

Write `demo-app/AgenticTodoDemo/Views/SettingsView.swift`:
```swift
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
```

**Step 2: Commit**

```bash
git add demo-app/AgenticTodoDemo/Views/SettingsView.swift
git commit -m "feat: add SettingsView with toggles, clear data, and sign out"
```

---

### Task 10: Create MainTabView

**Files:**
- Create: `demo-app/AgenticTodoDemo/Views/MainTabView.swift`

**Step 1: Write MainTabView.swift**

Write `demo-app/AgenticTodoDemo/Views/MainTabView.swift`:
```swift
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
```

**Step 2: Commit**

```bash
git add demo-app/AgenticTodoDemo/Views/MainTabView.swift
git commit -m "feat: add MainTabView with home and settings tabs"
```

---

### Task 11: Create App.swift entry point

**Files:**
- Create: `demo-app/AgenticTodoDemo/App.swift`

**Step 1: Write App.swift**

Write `demo-app/AgenticTodoDemo/App.swift`:
```swift
import SwiftUI

@main
struct AgenticTodoDemoApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            Group {
                if appState.isLoggedIn {
                    MainTabView()
                } else {
                    LoginView()
                }
            }
            .environmentObject(appState)
            .preferredColorScheme(appState.isDarkMode ? .dark : .light)
        }
    }
}
```

**Step 2: Commit**

```bash
git add demo-app/AgenticTodoDemo/App.swift
git commit -m "feat: add App.swift entry point with login gating and dark mode"
```

---

### Task 12: Generate Xcode project and verify build

**Step 1: Generate Xcode project**

```bash
cd ios-agentic-loop/demo-app && xcodegen generate
```

Expected: `Generated project AgenticTodoDemo.xcodeproj`

**Step 2: Build for simulator**

```bash
cd ios-agentic-loop/demo-app && xcodebuild \
  -project AgenticTodoDemo.xcodeproj \
  -scheme AgenticTodoDemo \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro' \
  build 2>&1 | tail -5
```

Expected: `** BUILD SUCCEEDED **`

**Step 3: Fix any compilation errors**

If the build fails, read the error output, fix the specific file, and rebuild. Common issues:
- Missing imports → add `import SwiftUI` or `import Foundation`
- Type mismatches → check the model matches the view expectations
- Accessibility identifier not compiling → ensure `.accessibilityIdentifier()` is on a `View`

**Step 4: Commit (only if fixes were needed)**

```bash
git add -A demo-app/AgenticTodoDemo/
git commit -m "fix: resolve build errors in demo app"
```

---

### Task 13: Create agentic-loop.config.yaml

**Files:**
- Create: `demo-app/agentic-loop.config.yaml`

**Step 1: Write config**

Write `demo-app/agentic-loop.config.yaml`:
```yaml
# Agentic Testing Loop Configuration for AgenticTodo Demo App

simulator:
  device: "iPhone 16 Pro"
  runtime: "iOS 18.2"
  udid: auto

app:
  bundle_id: "com.agentic-loop.demo"
  extension_bundle_ids: []
  build_command: "cd demo-app && xcodegen generate && xcodebuild -project AgenticTodoDemo.xcodeproj -scheme AgenticTodoDemo -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build"
  app_group: ""

idb:
  action_delay_ms: 700     # SwiftUI needs slightly longer delays
  describe_all_timeout_ms: 5000

loop:
  max_steps_per_goal: 30
  max_retries_per_action: 3
  verify_timeout_ms: 2000

maestro:
  output_dir: "demo-app/tests/maestro/flows"
  prefer_id_selectors: true
  include_ai_assertions: true

artifacts:
  results_dir: "demo-app/tests/agentic/results"
  keep_last_n_runs: 10
```

**Step 2: Commit**

```bash
git add demo-app/agentic-loop.config.yaml
git commit -m "config: add agentic-loop.config.yaml for demo app"
```

---

### Task 14: Create Maestro smoke test and config

**Files:**
- Create: `demo-app/tests/maestro/config.yaml`
- Create: `demo-app/tests/maestro/flows/smoke/app_launch.yaml`

**Step 1: Write Maestro config**

Write `demo-app/tests/maestro/config.yaml`:
```yaml
appId: "com.agentic-loop.demo"

tags:
  - smoke
  - regression

flows:
  - "flows/**/*.yaml"
```

**Step 2: Write smoke test**

Write `demo-app/tests/maestro/flows/smoke/app_launch.yaml`:
```yaml
appId: com.agentic-loop.demo
name: App Launch Smoke Test
tags:
  - smoke
  - regression
---
# Verify the app launches and shows the login screen

- launchApp:
    appId: "com.agentic-loop.demo"
    clearState: true

- waitForAnimationToEnd

# Verify login screen elements are visible
- assertVisible:
    id: "login_field_email"

- assertVisible:
    id: "login_field_password"

- assertVisible:
    id: "login_button_submit"

# Log in with test credentials
- tapOn:
    id: "login_field_email"
- inputText: "test@example.com"

- tapOn:
    id: "login_field_password"
- inputText: "password123"

- tapOn:
    id: "login_button_submit"

- waitForAnimationToEnd

# Verify main app loaded with tabs
- assertVisible:
    id: "tab_home"

- assertVisible:
    id: "tab_settings"

# Verify task list is visible
- assertVisible:
    id: "home_list_tasks"

- takeScreenshot: "smoke_app_launch"
```

**Step 3: Commit**

```bash
git add demo-app/tests/maestro/
git commit -m "test: add Maestro config and smoke test for demo app"
```

---

### Task 15: Write verification guide

**Files:**
- Create: `demo-app/VERIFICATION.md`

**Step 1: Write the guide**

Write `demo-app/VERIFICATION.md`:
```markdown
# Plugin Verification Guide

Step-by-step guide to verify every ios-agentic-loop plugin component using the AgenticTodo demo app.

## Prerequisites

1. macOS with Xcode 16+
2. XcodeGen: `brew install xcodegen`
3. idb: `pip3 install fb-idb` + `brew tap facebook/fb && brew install idb-companion`
4. Maestro: `curl -Ls 'https://get.maestro.mobile.dev' | bash`

Run the plugin's prerequisite check:

```bash
bash scripts/check-prerequisites.sh
```

## Step 1: Build and Install the Demo App

```bash
# Generate Xcode project
cd demo-app && xcodegen generate

# Boot simulator
bash ../scripts/boot-simulator.sh 'iPhone 16 Pro'

# Build the app
xcodebuild -project AgenticTodoDemo.xcodeproj \
  -scheme AgenticTodoDemo \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro' \
  build

# Find and install the built app
APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData/AgenticTodoDemo-*/Build/Products/Debug-iphonesimulator -name "AgenticTodoDemo.app" -type d | head -1)
xcrun simctl install booted "$APP_PATH"

# Launch to verify
xcrun simctl launch booted com.agentic-loop.demo
```

## Step 2: Plugin Setup (verifies /setup-project command)

The demo ships with a pre-configured `agentic-loop.config.yaml`. To test the setup command from scratch:

```
/setup-project
```

Enter when prompted:
- Bundle ID: `com.agentic-loop.demo`
- Build command: `cd demo-app && xcodebuild -project AgenticTodoDemo.xcodeproj -scheme AgenticTodoDemo -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build`

## Step 3: ORAV Exploration (verifies ui-explorer agent)

Ask Claude to explore the app autonomously:

```
Explore the AgenticTodo demo app. Start by logging in with any credentials, then explore all screens.
```

This invokes the `ui-explorer` agent which will:
1. Screenshot the login screen
2. Read the accessibility tree via `idb ui describe-all`
3. Type credentials and tap Sign In
4. Navigate through tabs
5. Interact with tasks, settings, and the add-task modal
6. Record every action to `/tmp/agentic/action_log.json`

**What to verify:**
- Agent takes screenshots at each step
- Agent reads accessibility tree JSON
- Agent computes tap coordinates from element frames
- Agent recovers from keyboard blocking or unexpected states

## Step 4: Goal-Directed Test (verifies goal mode)

Test a specific flow:

```
Test the login flow: enter email "user@test.com" and password "secret", tap sign in, verify the task list appears.
```

**What to verify:**
- Agent breaks the goal into sub-goals
- Agent tracks progress against success criteria
- Agent reports success/failure

## Step 5: Export to Maestro (verifies /export-maestro-flow command)

After exploration, export the recorded actions:

```
/export-maestro-flow
```

**What to verify:**
- Reads `/tmp/agentic/action_log.json`
- Generates a Maestro YAML flow file
- Uses `id:` selectors (from accessibility identifiers) over `text:` or `point:`

## Step 6: Run Maestro Tests (verifies /run-maestro command)

Run the smoke test:

```
/run-maestro
```

Or run directly:

```bash
maestro test demo-app/tests/maestro/flows/smoke/app_launch.yaml
```

**What to verify:**
- Maestro launches the app
- Login flow completes
- Tab assertions pass
- Screenshot captured

## Step 7: Accessibility Audit (verifies /audit-accessibility command)

```
/audit-accessibility
```

**What to verify:**
- Scans all `*View.swift` files in `demo-app/`
- Reports all interactive elements
- Flags any missing accessibility identifiers
- All elements should pass (demo app has full coverage)

## Step 8: Hook Verification (verifies PostToolUse hook)

Edit any View.swift file in the demo app — for example, add a new button without an accessibility identifier:

```swift
// In SettingsView.swift, add inside the "About" section:
Button("Rate App") {
    // no-op
}
```

**What to verify:**
- The PostToolUse hook fires after the Edit tool completes
- Claude warns about the missing `.accessibilityIdentifier()` on the new button
- Suggests adding `.accessibilityIdentifier("settings_button_rate")`

## Step 9: Reset Test State (verifies /reset-test-state command)

```
/reset-test-state
```

**What to verify:**
- Clears `/tmp/agentic/` directory
- Uninstalls and reinstalls the app (fresh state)
- Ready for another exploration run

## Plugin Component Coverage

| Component | Type | Verified In |
|-----------|------|-------------|
| ui-explorer | Agent | Steps 3, 4 |
| regression-runner | Agent | Step 6 |
| /check-prerequisites | Command | Prerequisites |
| /setup-project | Command | Step 2 |
| /audit-accessibility | Command | Step 7 |
| /run-maestro | Command | Step 6 |
| /reset-test-state | Command | Step 9 |
| /export-maestro-flow | Command | Step 5 |
| idb-exploration | Skill | Steps 3, 4 |
| accessibility-testing | Skill | Step 7 |
| maestro-testing | Skill | Steps 5, 6 |
| PostToolUse hook | Hook | Step 8 |
| check-prerequisites.sh | Script | Prerequisites |
| boot-simulator.sh | Script | Step 1 |
| Config template | Template | Step 2 |
| Maestro template | Template | Step 6 |
```

**Step 2: Commit**

```bash
git add demo-app/VERIFICATION.md
git commit -m "docs: add plugin verification guide for demo app"
```

---

### Task 16: Final integration test

**Step 1: Clean build from scratch**

```bash
cd ios-agentic-loop/demo-app
rm -rf AgenticTodoDemo.xcodeproj
xcodegen generate
xcodebuild -project AgenticTodoDemo.xcodeproj \
  -scheme AgenticTodoDemo \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro' \
  clean build 2>&1 | tail -5
```

Expected: `** BUILD SUCCEEDED **`

**Step 2: Install and launch on simulator**

```bash
APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData/AgenticTodoDemo-*/Build/Products/Debug-iphonesimulator -name "AgenticTodoDemo.app" -type d | head -1)
xcrun simctl install booted "$APP_PATH"
xcrun simctl launch booted com.agentic-loop.demo
```

Expected: App launches on simulator showing the login screen.

**Step 3: Take a verification screenshot**

```bash
xcrun simctl io booted screenshot /tmp/demo-app-verify.png
```

Read the screenshot to confirm the login screen is visible with email field, password field, and sign in button.

**Step 4: Final commit**

```bash
git add -A demo-app/
git commit -m "feat: complete AgenticTodo demo app for plugin verification"
```
