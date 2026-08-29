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
    @State private var showHistory = false
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

                composer
            }
            .navigationTitle("问答")
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
                                Text(apiStore.model).lineLimit(1)
                            }
                            .font(.footnote.weight(.medium))
                            .foregroundStyle(.orange)
                            .frame(maxWidth: 120)
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
                            Label(viewModel.modeLabel, systemImage: "slider.horizontal.3")
                            .font(.footnote.weight(.medium))
                            .foregroundStyle(EvilifeTheme.brandDark)
                        }
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button("新对话", systemImage: "square.and.pencil") { viewModel.clear() }
                        if appState.isLoggedIn {
                            Button("历史", systemImage: "clock.arrow.circlepath") { showHistory = true }
                            Button("退出登录", systemImage: "rectangle.portrait.and.arrow.right", role: .destructive) {
                                Task { await appState.logout() }
                            }
                        } else {
                            Button("登录", systemImage: "person.crop.circle") { showAuth = true }
                        }
                        Divider()
                        Button("API 接入", systemImage: "bolt.horizontal.circle") { showAPISettings = true }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .sheet(isPresented: $showAuth) { AuthView() }
            .sheet(isPresented: $showAPISettings) { APISettingsView() }
            .sheet(isPresented: $showHistory) { HistoryView() }
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
                Text("请配置视觉接口，或关闭直连模式。")
            }
            .photosPicker(isPresented: $showPhotoLibraryPicker, selection: $pickerItem, matching: .images)
        }
        .onChange(of: pickerItem) { _, newItem in
            Task {
                guard let newItem,
                      let data = try? await newItem.loadTransferable(type: Data.self) else { return }
                let mime = mimeType(for: newItem.supportedContentTypes.first?.preferredFilenameExtension)
                acceptPickedImage(data, filename: "photo.\(newItem.supportedContentTypes.first?.preferredFilenameExtension ?? "jpg")", mime: mime)
            }
        }
    }

    private var welcomeView: some View {
        VStack(spacing: 16) {
            Image(systemName: "heart.text.square")
                .font(.system(size: 38, weight: .medium))
                .foregroundStyle(EvilifeTheme.brand)
            Text("想了解什么？")
                .font(.title2.weight(.semibold))
            Text("结论 · 建议 · 来源")
                .font(.subheadline)
                .foregroundStyle(EvilifeTheme.textSecondary)
            VStack(spacing: 10) {
                ForEach(sampleQuestions, id: \.self) { question in
                    Button {
                        inputText = question
                        Task { await sendCurrent() }
                    } label: {
                        Text(question)
                            .font(.subheadline)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                            .background(EvilifeTheme.cardBg, in: RoundedRectangle(cornerRadius: 14))
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.top, 8)
        }
        .padding(.vertical, 48)
    }

    private let sampleQuestions = [
        "咖啡会升高血压吗？",
        "16:8 限时进食有用吗？",
        "每天能吃鸡蛋吗？",
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
                    Image(systemName: "plus")
                        .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(photoButtonUsable ? EvilifeTheme.brand : EvilifeTheme.textTertiary)
                    .frame(width: 40, height: 40)
                    .background(EvilifeTheme.cardBg, in: Circle())
                }
                .accessibilityLabel("添加照片")
                TextField("问健康问题", text: $inputText, axis: .vertical)
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
            .padding(.bottom, 8)
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
                        Text("失败：\(detail)")
                            .font(.footnote)
                            .foregroundStyle(EvilifeTheme.riskRefused)
                    }
                    if message.modules.isEmpty, message.text == nil, case .done = message.status {
                        Text("暂无结果")
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
        HStack(spacing: 8) {
            ProgressView().controlSize(.small)
            Text(statusText).font(.footnote).foregroundStyle(EvilifeTheme.textSecondary)
        }
        .padding(.vertical, 6)
    }

    private var statusText: String {
        switch message.status {
        case .waiting, .streaming: return "正在查证…"
        case .done: return "完成"
        case .failed: return "失败"
        }
    }

}

#Preview {
    ChatView().environmentObject(AppState())
}
