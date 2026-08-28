import SwiftUI
import PhotosUI
import UIKit

struct ChatView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = ChatViewModel()
    @StateObject private var apiStore = APIConfigStore.shared

    @State private var inputText = ""
    @State private var showAuth = false
    @State private var showAPISettings = false
    @State private var showCamera = false
    @State private var showVisionHint = false
    @State private var showPhotoLibraryPicker = false
    @State private var pickerItem: PhotosPickerItem?
    @State private var pendingImage: (Data, String, String)? // data, filename, mime
    @FocusState private var inputFocused: Bool

    private let modes = ["auto", "fast", "deep", "evaluation"]

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 14) {
                            if viewModel.messages.isEmpty {
                                welcomeView
                            }
                            ForEach(viewModel.messages) { message in
                                MessageRow(
                                    message: message,
                                    onSelectOption: { viewModel.sendOption($0) },
                                    onStartFast: {}
                                )
                                .id(message.id)
                            }
                            if viewModel.isSending {
                                HStack { Spacer(); ProgressView(); Spacer() }.padding(.vertical, 8)
                            }
                        }
                        .padding(16)
                    }
                    .onChange(of: viewModel.messages.count) {
                        if let last = viewModel.messages.last {
                            withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                        }
                    }
                }
                .background(EvilifeTheme.pageBg)

                if !appState.isLoggedIn {
                    guestBanner
                }

                composer
            }
            .navigationTitle("EviLife 循证问答")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    if apiStore.directEnabled {
                        Menu {
                            Picker("模型", selection: $apiStore.model) {
                                ForEach(apiStore.models, id: \.self) { name in
                                    Text(name).tag(name)
                                }
                            }
                            Picker("推理强度", selection: $apiStore.reasoningLevel) {
                                Text("简洁（低）").tag(0)
                                Text("标准（中）").tag(1)
                                Text("深入（高）").tag(2)
                            }
                            Toggle("视觉模型桥接", isOn: $apiStore.visionEnabled)
                            Divider()
                            Button("API 接入…", systemImage: "bolt.horizontal.circle") {
                                showAPISettings = true
                            }
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: "bolt.fill")
                                Text("直连 \(apiStore.model)")
                                Text("· \(apiStore.reasoningLabel)")
                            }
                            .font(.footnote.weight(.medium))
                            .foregroundStyle(.orange)
                        }
                    } else {
                        Menu {
                            ForEach(modes, id: \.self) { mode in
                                Button {
                                    viewModel.mode = mode
                                } label: {
                                    if viewModel.mode == mode {
                                        Label(modeLabel(mode), systemImage: "checkmark")
                                    } else {
                                        Text(modeLabel(mode))
                                    }
                                }
                            }
                        } label: {
                            HStack(spacing: 4) {
                                Text("模式")
                                Text(viewModel.modeLabel).foregroundStyle(EvilifeTheme.brand)
                            }
                            .font(.footnote.weight(.medium))
                        }
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button("API 接入", systemImage: "bolt.horizontal.circle") { showAPISettings = true }
                        Button("新对话", systemImage: "square.and.pencil") { viewModel.clear() }
                        if appState.isLoggedIn {
                            Button("退出登录", systemImage: "rectangle.portrait.and.arrow.right", role: .destructive) {
                                Task { await appState.logout() }
                            }
                        } else {
                            Button("登录 / 注册", systemImage: "person.crop.circle") { showAuth = true }
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .sheet(isPresented: $showAuth) { AuthView() }
            .sheet(isPresented: $showAPISettings) { APISettingsView() }
            .sheet(isPresented: $showCamera) {
                CameraPicker { image in
                    handleCameraImage(image)
                }
                .ignoresSafeArea()
            }
            .alert("需要视觉模型", isPresented: $showVisionHint) {
                Button("去配置", role: .cancel) { showAPISettings = true }
                Button("知道了") { }
            } message: {
                Text("直连模式下图片需要视觉模型才能识别。请先到 API 接入里配置视觉接口（地址 + Key + 模型），或关闭直连模式走 EviLife 后端。")
            }
            .photosPicker(isPresented: $showPhotoLibraryPicker, selection: $pickerItem, matching: .images)
        }
        .onChange(of: pickerItem) { newItem in
            Task {
                guard let newItem,
                      let data = try? await newItem.loadTransferable(type: Data.self) else { return }
                let mime = mimeType(for: newItem.supportedContentTypes.first?.preferredFilenameExtension)
                acceptPickedImage(data, filename: "photo.\(newItem.supportedContentTypes.first?.preferredFilenameExtension ?? "jpg")", mime: mime)
            }
        }
    }

    private var welcomeView: some View {
        VStack(spacing: 14) {
            Image(systemName: "cross.case.fill")
                .font(.system(size: 44))
                .foregroundStyle(EvilifeTheme.brand)
            Text("问一个健康问题")
                .font(.title3.weight(.semibold))
            Text("EviLife 会先检索本地循证语料与医学文献，再给出带引用的结论、证据分级与「是 / 部分正确 / 否 / 证据不足」裁决。")
                .font(.footnote)
                .foregroundStyle(EvilifeTheme.textSecondary)
                .multilineTextAlignment(.center)
            VStack(spacing: 8) {
                ForEach(sampleQuestions, id: \.self) { question in
                    Button {
                        inputText = question
                        Task { await sendCurrent() }
                    } label: {
                        Text(question)
                            .font(.footnote)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(12)
                            .background(EvilifeTheme.cardBg, in: RoundedRectangle(cornerRadius: 12))
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.top, 6)
        }
        .padding(.vertical, 36)
    }

    private let sampleQuestions = [
        "每天喝咖啡会升高血压吗？",
        "限盐真的能降血压吗？",
        "16:8 限时进食能减肥吗？",
        "鸡蛋会升高心血管风险吗？",
    ]

    private var composer: some View {
        VStack(spacing: 8) {
            if let pendingImage {
                HStack {
                    if let uiImage = UIImage(data: pendingImage.0) {
                        Image(uiImage: uiImage)
                            .resizable().scaledToFill()
                            .frame(width: 56, height: 56)
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                    }
                    Text("图片已附加，点右侧箭头发送")
                        .font(.footnote).foregroundStyle(EvilifeTheme.textSecondary)
                    Spacer()
                    Button {
                        self.pendingImage = nil
                    } label: {
                        Image(systemName: "xmark.circle.fill").foregroundStyle(EvilifeTheme.textTertiary)
                    }
                }
                .padding(.horizontal, 14)
            }
            HStack(alignment: .bottom, spacing: 10) {
                Menu {
                    Button {
                        showCamera = true
                    } label: {
                        Label("拍照", systemImage: "camera.fill")
                    }
                    Button {
                        showPhotoLibraryPicker = true
                    } label: {
                        Label("从相册选择", systemImage: "photo.on.rectangle")
                    }
                } label: {
                    VStack(spacing: 2) {
                        Image(systemName: "photo.badge.plus")
                            .font(.system(size: 20))
                        Text("照片")
                            .font(.caption2)
                    }
                    .foregroundStyle(photoButtonUsable ? EvilifeTheme.brand : EvilifeTheme.textTertiary)
                    .frame(width: 40, height: 40)
                }
                TextField("输入健康问题，或附上一张餐食照片", text: $inputText, axis: .vertical)
                    .lineLimit(1...5)
                    .focused($inputFocused)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(EvilifeTheme.cardBg, in: RoundedRectangle(cornerRadius: 16))
                Button {
                    Task { await sendCurrent() }
                } label: {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.system(size: 30))
                        .foregroundStyle(canSend ? EvilifeTheme.brand : EvilifeTheme.textTertiary)
                }
                .disabled(!canSend)
            }
            .padding(.horizontal, 14)
            Text(AppConfig.medicalDisclaimer)
                .font(.caption2)
                .foregroundStyle(EvilifeTheme.textTertiary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 20)
                .padding(.bottom, 6)
        }
        .padding(.top, 8)
        .background(.bar)
    }

    private var canSend: Bool {
        !viewModel.isSending && (!inputText.trimmingCharacters(in: .whitespaces).isEmpty || pendingImage != nil)
    }

    /// 照片按钮是否可用：直连模式下需要已配置视觉模型。
    private var photoButtonUsable: Bool {
        if apiStore.directEnabled {
            return apiStore.visionEnabled && apiStore.hasVisionKey
        }
        return true
    }

    /// 校验后把图片放入待发送附件；直连模式无视觉模型时提示配置。
    private func acceptPickedImage(_ data: Data, filename: String, mime: String) {
        if apiStore.directEnabled && !photoButtonUsable {
            showVisionHint = true
            return
        }
        pendingImage = (data, filename, mime)
    }

    private func handleCameraImage(_ image: UIImage) {
        guard let data = image.jpegData(compressionQuality: 0.85) else { return }
        acceptPickedImage(data, filename: "camera.jpg", mime: "image/jpeg")
    }

    private func sendCurrent() async {
        let text = inputText
        inputText = ""
        inputFocused = false
        let image = pendingImage
        pendingImage = nil
        if apiStore.directEnabled {
            await viewModel.sendDirect(text: text, imageData: image?.0, imageMime: image?.2)
        } else {
            await viewModel.send(text: text, imageData: image?.0, imageName: image?.1, imageMime: image?.2)
        }
    }

    private var guestBanner: some View {
        HStack {
            Image(systemName: "person.crop.circle.badge.questionmark")
            Text("当前为游客模式，历史不会同步到账号。")
                .font(.caption)
            Spacer()
            Button("登录") { showAuth = true }
                .font(.caption.weight(.semibold))
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(EvilifeTheme.brandLight)
        .overlay(alignment: .top) { Rectangle().fill(EvilifeTheme.brand.opacity(0.3)).frame(height: 1) }
    }

    private func modeLabel(_ mode: String) -> String {
        switch mode {
        case "fast": return "快速"
        case "deep": return "深度"
        case "evaluation": return "评估"
        default: return "自动"
        }
    }

    private func mimeType(for ext: String?) -> String {
        switch ext?.lowercased() {
        case "png": return "image/png"
        case "webp": return "image/webp"
        default: return "image/jpeg"
        }
    }
}

// MARK: - Message row

struct MessageRow: View {
    let message: ChatViewModel.Message
    let onSelectOption: (String) -> Void
    let onStartFast: () -> Void

    var body: some View {
        switch message.role {
        case .user:
            HStack {
                Spacer(minLength: 48)
                VStack(alignment: .trailing, spacing: 6) {
                    if let imageData = message.imageData, let uiImage = UIImage(data: imageData) {
                        Image(uiImage: uiImage)
                            .resizable().scaledToFit()
                            .frame(maxHeight: 220)
                            .clipShape(RoundedRectangle(cornerRadius: 14))
                    }
                    if let text = message.text {
                        Text(text)
                            .font(.body)
                            .foregroundStyle(.white)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 10)
                            .background(EvilifeTheme.brand, in: RoundedRectangle(cornerRadius: 18))
                    }
                }
            }
        case .assistant:
            HStack {
                VStack(alignment: .leading, spacing: 10) {
                    if message.status != .done {
                        statusRow
                    }
                    if let text = message.text, message.modules.isEmpty {
                        Text(text)
                            .font(.body)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(14)
                            .background(EvilifeTheme.cardBg, in: RoundedRectangle(cornerRadius: 18))
                    }
                    ForEach(message.modules) { module in
                        ModuleCardView(module: module, onSelectOption: onSelectOption)
                    }
                    if case .failed(let detail) = message.status {
                        Text("请求失败：\(detail)")
                            .font(.footnote)
                            .foregroundStyle(EvilifeTheme.riskRefused)
                    }
                    if message.modules.isEmpty, message.text == nil, case .done = message.status {
                        Text("没有可展示的模块。")
                            .font(.footnote)
                            .foregroundStyle(EvilifeTheme.textTertiary)
                    }
                }
                Spacer(minLength: 32)
            }
        }
    }

    @ViewBuilder
    private var statusRow: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text(statusText).font(.footnote).foregroundStyle(EvilifeTheme.textSecondary)
            }
            if let route = message.route {
                Text("路径：\(routeLabel(route))")
                    .font(.caption2)
                    .foregroundStyle(EvilifeTheme.textTertiary)
            }
        }
        .padding(12)
        .background(EvilifeTheme.cardBg, in: RoundedRectangle(cornerRadius: 14))
    }

    private var statusText: String {
        switch message.status {
        case .waiting: return "正在编排证据任务…"
        case .streaming: return "正在检索与核验证据…"
        case .done: return "完成"
        case .failed: return "失败"
        }
    }

    private func routeLabel(_ route: String) -> String {
        switch route {
        case "fast_path": return "证据包快查"
        case "deep_path": return "深度双向检索"
        case "general": return "通用问答"
        case "rag": return "RAG 检索"
        case "safety_refusal": return "安全拦截"
        case "injection_refusal": return "注入拦截"
        default: return route
        }
    }
}

#Preview {
    ChatView().environmentObject(AppState())
}
