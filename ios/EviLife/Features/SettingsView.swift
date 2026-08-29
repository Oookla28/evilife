import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @State private var showAuth = false
    @State private var serverURL = AppConfig.baseURL

    var body: some View {
        NavigationStack {
            Form {
                accountSection
                aboutSection
                serverSection
            }
            .navigationTitle("设置")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") { dismiss() }
                }
            }
            .sheet(isPresented: $showAuth) { AuthView() }
        }
    }

    private var accountSection: some View {
        Section("账号") {
            if let user = appState.user {
                LabeledContent(user.display_name, value: user.email)
                Button("退出登录", role: .destructive) {
                    Task { await appState.logout() }
                }
            } else {
                Button {
                    showAuth = true
                } label: {
                    HStack {
                        Image(systemName: "person.crop.circle.badge.plus").foregroundStyle(EvilifeTheme.brand)
                        Text("登录")
                    }
                }
                Text("登录后同步记录")
                    .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
            }
        }
    }

    private var serverSection: some View {
        Section("高级") {
            DisclosureGroup("服务器") {
                TextField("服务器地址", text: $serverURL)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Button("保存") {
                    AppConfig.setBaseURL(serverURL)
                    appState.showToast("已保存")
                }
            }
        }
    }

    private var aboutSection: some View {
        Section("关于") {
            LabeledContent("EviLife", value: "1.0")
            DisclosureGroup("医疗与隐私") {
                Text(AppConfig.medicalDisclaimer)
                Text("健康数据仅在你授权后读取和同步。")
            }
            .font(.footnote)
            .foregroundStyle(EvilifeTheme.textSecondary)
        }
    }
}

#Preview {
    SettingsView().environmentObject(AppState())
}
