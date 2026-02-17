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
