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
                    Toggle("直连 API", isOn: $store.directEnabled)
                    Text("直连回答不含循证引用。")
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
                    Text("支持 OpenAI 兼容接口。")
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
                        if removed.contains(store.model), let first = store.models.first {
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
                                Text("读取中…")
                            } else {
                                Text("读取模型")
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
                    Text("可在问答页切换模型与强度。")
                }

                Section {
                    Toggle("图片识别", isOn: $store.visionEnabled)
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
                    Text("视觉模型")
                } footer: {
                    Text("用于直连模式的图片识别。")
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
                                Text("测试连接")
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
                    Text("Key 仅保存在本机。直连回答不含证据核验。")
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
