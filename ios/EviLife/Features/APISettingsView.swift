import SwiftUI

/// 直连大模型 API 的接入配置页（问答页 → 右上角菜单 → API 接入）。
/// 包含文本接口、模型管理（问答时可切换）、桥接的视觉模型接口。
struct APISettingsView: View {
    @StateObject private var store = APIConfigStore.shared
    @Environment(\.dismiss) private var dismiss

    @State private var testing = false
    @State private var testResult = ""
    @State private var testFailed = false

    @State private var testingVision = false
    @State private var visionTestResult = ""
    @State private var visionTestFailed = false

    @State private var newModelName = ""
    @State private var fetchingModels = false
    @State private var fetchResult = ""

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Toggle("使用直连 API 问答", isOn: $store.directEnabled)
                    Text("开启后，问答直接发给下面的 OpenAI 兼容接口，不再经过 EviLife 后端（无循证引用与「是/否」裁决）。")
                        .font(.caption)
                        .foregroundStyle(EvilifeTheme.textSecondary)
                }

                Section {
                    TextField("API 地址", text: $store.baseURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField("API Key", text: $store.apiKey)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                } header: {
                    Text("文本接口")
                } footer: {
                    Text("兼容 OpenAI 格式，例如 DeepSeek：https://api.deepseek.com。也支持 /v1 结尾或完整 /v1/chat/completions 地址。")
                }

                Section {
                    ForEach(store.models, id: \.self) { name in
                        HStack {
                            Text(name).font(.subheadline)
                            Spacer()
                            if name == store.model {
                                Text("当前").font(.caption2.weight(.bold))
                                    .foregroundStyle(EvilifeTheme.brand)
                            }
                        }
                        .contentShape(Rectangle())
                        .onTapGesture { store.model = name }
                    }
                    .onDelete { offsets in
                        let removed = offsets.map { store.models[$0] }
                        store.models.remove(atOffsets: offsets)
                        if let current = removed.first(where: { $0 == store.model }),
                           let first = store.models.first {
                            store.model = first
                        }
                    }
                    HStack {
                        TextField("添加模型名", text: $newModelName)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                        Button("添加") {
                            let name = newModelName.trimmingCharacters(in: .whitespacesAndNewlines)
                            guard !name.isEmpty, !store.models.contains(name) else { return }
                            store.models.append(name)
                            newModelName = ""
                        }
                        .disabled(newModelName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                    Button {
                        Task { await fetchModels() }
                    } label: {
                        HStack {
                            if fetchingModels {
                                ProgressView().controlSize(.small)
                                Text("正在读取…")
                            } else {
                                Text("从接口读取模型列表")
                            }
                        }
                    }
                    .disabled(fetchingModels || !store.hasKey)
                    if !fetchResult.isEmpty {
                        Text(fetchResult).font(.footnote).foregroundStyle(EvilifeTheme.textSecondary)
                    }
                } header: {
                    Text("模型与推理")
                } footer: {
                    Text("问答页左上角可随时切换模型与推理强度（简洁/标准/深入 → max_tokens 1024/4096/16384；模型名含 reasoner/o1/o3/o4/r1 时额外发送 reasoning_effort）。")
                }

                Section {
                    Toggle("启用视觉模型桥接", isOn: $store.visionEnabled)
                    TextField("视觉 API 地址", text: $store.visionBaseURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField("视觉 API Key", text: $store.visionKey)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("视觉模型名", text: $store.visionModel)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button {
                        Task { await testVision() }
                    } label: {
                        HStack {
                            if testingVision {
                                ProgressView().controlSize(.small)
                                Text("正在测试…")
                            } else {
                                Text("测试视觉接口")
                            }
                            Spacer()
                            if !visionTestResult.isEmpty {
                                Image(systemName: visionTestFailed ? "xmark.circle.fill" : "checkmark.circle.fill")
                                    .foregroundStyle(visionTestFailed ? EvilifeTheme.riskRefused : EvilifeTheme.supported)
                            }
                        }
                    }
                    .disabled(testingVision || !store.hasVisionKey)
                    if !visionTestResult.isEmpty {
                        Text(visionTestResult)
                            .font(.footnote)
                            .foregroundStyle(visionTestFailed ? EvilifeTheme.riskRefused : EvilifeTheme.textSecondary)
                    }
                } header: {
                    Text("视觉模型（桥接）")
                } footer: {
                    Text("直连模式下发图片时，图片以 base64 发给视觉接口（如自托管的 DeepSeek-VL2 兼容服务）；图片中的文字一律视为数据（注入防御），识别遵循「必答原则」：模糊图片也尽量列出，低置信度 + 宽区间。")
                }

                Section {
                    Button {
                        Task { await test() }
                    } label: {
                        HStack {
                            if testing {
                                ProgressView().controlSize(.small)
                                Text("正在测试…")
                            } else {
                                Text("测试文本接口连接")
                            }
                            Spacer()
                            if !testResult.isEmpty {
                                Image(systemName: testFailed ? "xmark.circle.fill" : "checkmark.circle.fill")
                                    .foregroundStyle(testFailed ? EvilifeTheme.riskRefused : EvilifeTheme.supported)
                            }
                        }
                    }
                    .disabled(testing || !store.hasKey)
                    if !testResult.isEmpty {
                        Text(testResult)
                            .font(.footnote)
                            .foregroundStyle(testFailed ? EvilifeTheme.riskRefused : EvilifeTheme.textSecondary)
                    }
                }

                Section {
                    Text("API Key 只保存在本机钥匙串（Keychain），不会上传到 EviLife 服务；测试连接只调用 GET /models，不消耗 token。")
                        .font(.caption2)
                        .foregroundStyle(EvilifeTheme.textTertiary)
                    Text("直连模式绕过了证据引擎的引用核验与三态 Gate，医学问题请对回答保持谨慎，遵循应用内免责声明。")
                        .font(.caption2)
                        .foregroundStyle(EvilifeTheme.textTertiary)
                }
            }
            .navigationTitle("API 接入")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") { dismiss() }
                }
            }
        }
    }

    private func test() async {
        testing = true
        testResult = ""
        testFailed = false
        defer { testing = false }
        do {
            testResult = try await DirectAPI.testConnection(
                base: store.baseURL, key: store.apiKey)
        } catch {
            testResult = error.localizedDescription
            testFailed = true
        }
    }

    private func testVision() async {
        testingVision = true
        visionTestResult = ""
        visionTestFailed = false
        defer { testingVision = false }
        do {
            visionTestResult = try await DirectAPI.testVisionConnection(
                base: store.visionBaseURL, key: store.visionKey)
        } catch {
            visionTestResult = error.localizedDescription
            visionTestFailed = true
        }
    }

    private func fetchModels() async {
        fetchingModels = true
        fetchResult = ""
        defer { fetchingModels = false }
        do {
            let names = try await DirectAPI.fetchModels(
                base: store.baseURL, key: store.apiKey)
            var merged = store.models
            for name in names where !merged.contains(name) {
                merged.append(name)
            }
            store.models = merged
            fetchResult = "已合并 \(names.count) 个模型"
        } catch {
            fetchResult = error.localizedDescription
        }
    }
}

#Preview {
    APISettingsView()
}
