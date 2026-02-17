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
