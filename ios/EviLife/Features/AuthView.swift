import SwiftUI

struct AuthView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var isRegister = false
    @State private var email = ""
    @State private var password = ""
    @State private var displayName = ""
    @State private var errorMessage = ""
    @State private var busy = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("邮箱", text: $email)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField("密码（至少 10 位，含字母和数字）", text: $password)
                    if isRegister {
                        TextField("昵称", text: $displayName)
                    }
                } header: {
                    Text(isRegister ? "注册 EviLife 账号" : "登录 EviLife 账号")
                } footer: {
                    if !errorMessage.isEmpty {
                        Text(errorMessage).foregroundStyle(EvilifeTheme.riskRefused)
                    }
                }

                Section {
                    Button {
                        Task { await submit() }
                    } label: {
                        if busy {
                            ProgressView().frame(maxWidth: .infinity)
                        } else {
                            Text(isRegister ? "注册并登录" : "登录").frame(maxWidth: .infinity)
                        }
                    }
                    .disabled(busy || email.isEmpty || password.isEmpty)
                }

                Section {
                    Button("没有账号？去注册") { isRegister.toggle() }
                    if isRegister {
                        Button("已有账号？去登录") { isRegister = false }
                    }
                }
                .font(.footnote)

                Section {
                    Text("游客也可以使用问答与记录功能；登录后可在多设备间同步对话历史。")
                        .font(.footnote)
                        .foregroundStyle(EvilifeTheme.textTertiary)
                }
            }
            .navigationTitle(isRegister ? "注册" : "登录")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
            }
        }
        .interactiveDismissDisabled(busy)
    }

    private func submit() async {
        busy = true
        errorMessage = ""
        defer { busy = false }
        do {
            if isRegister {
                try await appState.register(email: email, password: password, name: displayName)
            } else {
                try await appState.login(email: email, password: password)
            }
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

#Preview {
    AuthView().environmentObject(AppState())
}
