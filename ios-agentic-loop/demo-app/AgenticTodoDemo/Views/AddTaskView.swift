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
