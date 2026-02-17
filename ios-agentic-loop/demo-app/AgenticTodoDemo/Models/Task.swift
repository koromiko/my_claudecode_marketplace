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
