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
