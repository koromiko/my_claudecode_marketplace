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
