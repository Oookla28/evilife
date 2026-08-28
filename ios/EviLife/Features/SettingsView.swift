import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @State private var showAuth = false
    @State private var serverURL = AppConfig.baseURL

    var body: some View {
        NavigationStack {
            Form {
                accountSection
                serverSection
                aboutSection
                disclaimerSection
            }
            .navigationTitle("设置")
            .sheet(isPresented: $showAuth) { AuthView() }
        }
    }

    private var accountSection: some View {
        Section("账号") {
            if let user = appState.user {
                LabeledContent("昵称", value: user.display_name)
                LabeledContent("邮箱", value: user.email)
                Button("退出登录", role: .destructive) {
                    Task { await appState.logout() }
                }
            } else {
                Button {
                    showAuth = true
                } label: {
                    HStack {
                        Image(systemName: "person.crop.circle.badge.plus").foregroundStyle(EvilifeTheme.brand)
                        Text("登录 / 注册 EviLife 账号")
                    }
                }
                Text("当前为游客模式：问答与记录仍可用，但不会同步到账号。")
                    .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
            }
        }
    }

    private var serverSection: some View {
        Section {
            TextField("例如 http://127.0.0.1:8010", text: $serverURL)
                .keyboardType(.URL)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
            Button("保存服务器地址") {
                AppConfig.setBaseURL(serverURL)
                appState.showToast("已保存，将在新请求中生效")
            }
        } header: {
            Text("服务器")
        } footer: {
            Text("开发环境默认连接本机 FastAPI（http://127.0.0.1:8010）。真机调试请改为 Mac 的局域网地址，并确保后端允许该来源。")
        }
    }

    private var aboutSection: some View {
        Section("关于") {
            LabeledContent("应用", value: "EviLife")
            LabeledContent("版本", value: "1.0 (iOS)")
            LabeledContent("定位", value: "循证健康问答与健康档案")
            VStack(alignment: .leading, spacing: 6) {
                Text("EviLife 是双模式循证健康平台：生活版用易懂语言解释健康问题；专业版按临床问题进行双向文献检索、证据分级与主张级引用。")
                    .font(.footnote)
                    .foregroundStyle(EvilifeTheme.textSecondary)
                Text("本 iOS 应用通过 HealthKit 把用户逐类授权的步数、睡眠、静息心率与体重聚合值同步到 EviLife 服务；Apple 账户只负责身份认证，健康数据权限始终由 HealthKit 单独控制。")
                    .font(.footnote)
                    .foregroundStyle(EvilifeTheme.textSecondary)
            }
        }
    }

    private var disclaimerSection: some View {
        Section {
            Text(AppConfig.medicalDisclaimer)
                .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
            Text("AI 输出必须先声明问题是否属于医疗健康范围；涉及伤害、违法、欺诈、隐私侵犯等操作性请求会被确定性的伦理闸门拒绝。")
                .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
        }
    }
}

#Preview {
    SettingsView().environmentObject(AppState())
}
