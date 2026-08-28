import SwiftUI

struct HealthView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var sync = HealthKitSyncService()
    @State private var profile: ProfileAnalysisResponse?
    @State private var connectors: [HealthConnector] = []
    @State private var analyzing = false
    @State private var errorMessage = ""

    @State private var showScanner = false
    @State private var pairingBusy = false
    @State private var pairingMessage = ""
    @State private var pairingError = ""
    @State private var manualCode = ""
    @State private var pendingPayload: PairingPayload?
    @State private var showPairingChoice = false
    @State private var transferring = false
    @State private var webSyncing = false

    var body: some View {
        NavigationStack {
            List {
                pairingSection
                healthKitSection
                profileSection
                connectorsSection
                disclaimerSection
            }
            .listStyle(.insetGrouped)
            .navigationTitle("健康")
            .task { await loadConnectors() }
            .sheet(isPresented: $showScanner) {
                NavigationStack {
                    ZStack {
                        QRScannerView { raw in
                            handleScan(raw)
                        }
                        .ignoresSafeArea()
                        VStack {
                            Spacer()
                            Text("将网页端的配对二维码对准取景框")
                                .font(.footnote.weight(.medium))
                                .padding(.horizontal, 14).padding(.vertical, 8)
                                .background(.regularMaterial, in: Capsule())
                                .padding(.bottom, 40)
                        }
                    }
                    .navigationTitle("扫码绑定网页端")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("取消") { showScanner = false }
                        }
                    }
                }
            }
        }
    }

    // MARK: 扫码绑定网页端（手表数据同步入口）

    private var pairingSection: some View {
        Section {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: "qrcode.viewfinder")
                        .font(.title3)
                        .foregroundStyle(EvilifeTheme.brand)
                    Text("网页端同步")
                        .font(.subheadline.weight(.semibold))
                    Spacer()
                    if let user = appState.user {
                        Text("已绑定").font(.caption2.weight(.bold))
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(EvilifeTheme.brandLight, in: Capsule())
                            .foregroundStyle(EvilifeTheme.brandDark)
                    }
                }
                if let user = appState.user {
                    Text("账号：\(user.email)（\(user.display_name)）。手机 HealthKit（含 Apple Watch 手表数据）同步将写入该账号，网页端登录同一账号即可看到。")
                        .font(.caption)
                        .foregroundStyle(EvilifeTheme.textSecondary)
                } else {
                    Text("网页端登录后生成配对二维码，手机扫码即绑定同一账号；之后手表/健康数据同步到账号，网页端直接可见。")
                        .font(.caption)
                        .foregroundStyle(EvilifeTheme.textSecondary)
                }
                if pairingBusy {
                    HStack(spacing: 8) {
                        ProgressView().controlSize(.small)
                        Text("正在绑定…").font(.footnote)
                    }
                }
                if !pairingMessage.isEmpty {
                    Text(pairingMessage).font(.footnote).foregroundStyle(EvilifeTheme.brandDark)
                }
                if !pairingError.isEmpty {
                    Text(pairingError).font(.footnote).foregroundStyle(EvilifeTheme.riskRefused)
                }
                Button {
                    showScanner = true
                } label: {
                    Label(appState.user != nil ? "重新扫码绑定" : "扫码绑定网页端", systemImage: "qrcode")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(EvilifeTheme.brand)
                .disabled(pairingBusy)

                HStack(spacing: 8) {
                    TextField("或手动输入配对码", text: $manualCode)
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()
                        .padding(.horizontal, 10).padding(.vertical, 8)
                        .background(EvilifeTheme.cardBg, in: RoundedRectangle(cornerRadius: 10))
                    Button("绑定") {
                        let code = manualCode.uppercased().filter { $0.isLetter || $0.isNumber }
                        guard (4...16).contains(code.count) else { return }
                        manualCode = ""
                        pairingError = ""
                        pairingMessage = ""
                        pendingPayload = PairingPayload(code: code, baseURL: nil, pairingURL: nil)
                        showPairingChoice = true
                    }
                    .disabled(pairingBusy || manualCode.uppercased().filter { $0.isLetter || $0.isNumber }.count < 4)
                }

                transferSection
                webSyncSection
            }
        } header: {
            Text("与网页端同步")
        } footer: {
            Text("配对码一次性有效，5 分钟内使用。绑定并登录＝手机登录为该账号；仅传输数据＝保留手机当前登录，把健康/手表数据传到对方账号。只扫描自己信任的二维码。")
        }
        .confirmationDialog("选择配对方式", isPresented: $showPairingChoice, titleVisibility: .visible) {
            Button("绑定并登录该账号") {
                if let payload = pendingPayload {
                    Task { await claim(code: payload.code ?? "", fallbackBase: payload.baseURL, mode: "login") }
                }
            }
            Button("仅传输数据到该账号（保留当前登录）") {
                if let payload = pendingPayload {
                    Task { await claim(code: payload.code ?? "", fallbackBase: payload.baseURL, mode: "transfer") }
                }
            }
            Button("取消", role: .cancel) { pendingPayload = nil }
        }
    }

    // MARK: 网页端 pairing_url 连接（douyin-spark 等自定义网页端）

    @ViewBuilder
    private var webSyncSection: some View {
        if let link = WebSyncLinkStore.load() {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 6) {
                    Image(systemName: "globe.asia.australia.fill")
                        .foregroundStyle(.blue)
                    Text("已连接网页端（\(link.dataURL)）")
                        .font(.footnote.weight(.medium))
                        .lineLimit(2)
                }
                Text("点下面按钮把 HealthKit（含 Apple Watch 手表）聚合数据上传到该网页端。")
                    .font(.caption)
                    .foregroundStyle(EvilifeTheme.textSecondary)
                if webSyncing {
                    HStack(spacing: 8) {
                        ProgressView().controlSize(.small)
                        Text("正在上传…").font(.footnote)
                    }
                }
                HStack(spacing: 10) {
                    Button {
                        Task { await syncToWeb(link: link) }
                    } label: {
                        Label("上传手表数据到网页端", systemImage: "icloud.and.arrow.up.fill")
                            .font(.footnote.weight(.medium))
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.blue)
                    .disabled(webSyncing || sync.syncing)
                    Button("断开") {
                        WebSyncLinkStore.save(nil)
                    }
                    .font(.footnote)
                    .foregroundStyle(EvilifeTheme.riskRefused)
                }
            }
            .padding(.vertical, 2)
        }
    }

    private func syncToWeb(link: WebSyncLink) async {
        webSyncing = true
        defer { webSyncing = false }
        do {
            let observations = try await sync.buildObservations(days: 30)
            let result = try await WebSyncClient.upload(
                dataURL: link.dataURL, token: link.token, observations: observations)
            pairingMessage = "已上传 \(result.accepted) 条手表健康数据到网页端（累计 \(result.total) 条）。"
            pairingError = ""
        } catch {
            pairingError = error.localizedDescription
        }
    }

    private func pairWithWeb(_ url: String) async {
        pairingBusy = true
        defer { pairingBusy = false }
        do {
            let link = try await WebSyncClient.pair(url: url)
            WebSyncLinkStore.save(WebSyncLink(token: link.token, dataURL: link.dataURL, savedAt: Date()))
            pairingError = ""
            pairingMessage = "已与网页端配对。正在上传手表健康数据…"
            let observations = try await sync.buildObservations(days: 30)
            let result = try await WebSyncClient.upload(
                dataURL: link.dataURL, token: link.token, observations: observations)
            pairingMessage = "已与网页端配对并上传 \(result.accepted) 条手表健康数据（累计 \(result.total) 条）。"
        } catch {
            pairingError = error.localizedDescription
        }
    }

    // MARK: 跨账号传输目标

    @ViewBuilder
    private var transferSection: some View {
        if let link = TransferLinkStore.load() {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 6) {
                    Image(systemName: "arrow.left.arrow.right.circle.fill")
                        .foregroundStyle(EvilifeTheme.partly)
                    Text("传输目标：\(link.targetEmail)（\(link.targetName)）")
                        .font(.footnote.weight(.medium))
                }
                Text("你的账号登录不受影响；点下面按钮会把 HealthKit（含手表）数据传到该账号，网页端用该账号登录即可看到。")
                    .font(.caption)
                    .foregroundStyle(EvilifeTheme.textSecondary)
                if transferring {
                    HStack(spacing: 8) {
                        ProgressView().controlSize(.small)
                        Text("正在同步并传输…").font(.footnote)
                    }
                }
                HStack(spacing: 10) {
                    Button {
                        Task { await syncAndTransfer(link: link) }
                    } label: {
                        Label("同步并传输手表数据", systemImage: "arrow.right.circle.fill")
                            .font(.footnote.weight(.medium))
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(EvilifeTheme.partly)
                    .disabled(transferring || sync.syncing)
                    Button("断开") {
                        TransferLinkStore.save(nil)
                    }
                    .font(.footnote)
                    .foregroundStyle(EvilifeTheme.riskRefused)
                }
            }
            .padding(.vertical, 2)
        }
    }

    private func syncAndTransfer(link: TransferLink) async {
        transferring = true
        defer { transferring = false }
        do {
            let observations = try await sync.buildObservations(days: 30)
            let response = try await API.transferDeviceData(
                token: link.token,
                consentReceipt: "healthkit-transfer-\(UUID().uuidString)",
                observations: observations)
            pairingMessage = "已把 \(response.accepted) 条记录传输到 \(link.targetEmail)（跳过 \(response.skipped) 条）。"
            pairingError = ""
        } catch {
            pairingError = error.localizedDescription
            if let parsed = error as? APIRequestError, case .http(404, _) = parsed {
                TransferLinkStore.save(nil) // 令牌失效即断开
            }
        }
    }

    private func handleScan(_ raw: String) {
        showScanner = false
        pairingError = ""
        pairingMessage = ""
        guard let payload = PairingParser.parse(raw) else {
            let preview = String(raw.prefix(60))
            pairingError = "无法识别的二维码内容：\(preview)（请确认扫的是 EviLife 网页端的配对二维码）"
            return
        }
        // 网页端自定义格式：{"pairing_url": "…"} → 直接配对 + 上传
        if let pairingURL = payload.pairingURL {
            Task { await pairWithWeb(pairingURL) }
            return
        }
        pendingPayload = payload
        showPairingChoice = true
    }

    private func claim(code: String, fallbackBase: String? = nil, mode: String = "login") async {
        pairingBusy = true
        defer { pairingBusy = false }
        do {
            try await performClaim(code: code, mode: mode)
        } catch {
            // 当前服务器 claim 失败时，若二维码带了 base_url 则切换后重试一次。
            if let fallback = fallbackBase, !fallback.isEmpty, fallback != AppConfig.baseURL {
                AppConfig.setBaseURL(fallback)
                do {
                    try await performClaim(code: code, mode: mode)
                    pairingMessage += "（服务器已切换到 \(fallback)）"
                } catch {
                    pairingError = error.localizedDescription
                }
                return
            }
            pairingError = error.localizedDescription
        }
    }

    private func performClaim(code: String, mode: String) async throws {
        let response = try await API.claimDevicePairing(code: code, mode: mode)
        if response.mode == "transfer",
           let token = response.transfer_token,
           let target = response.target {
            let expiresAt = Date().addingTimeInterval(TimeInterval(response.expires_in ?? 86400))
            TransferLinkStore.save(TransferLink(
                token: token,
                targetEmail: target.email,
                targetName: target.display_name,
                expiresAt: expiresAt))
            pairingMessage = "已连接传输目标 \(target.email)（24 小时内有效）。点「同步并传输手表数据」即可跨账号传输。"
            pairingError = ""
        } else if let user = response.user {
            appState.user = user
            pairingMessage = "已绑定 \(user.email)。授权 HealthKit 并点下方「同步最近 30 天数据」，手表数据就会出现在网页端。"
            pairingError = ""
        } else {
            pairingError = "服务器响应无法解析"
        }
    }

    // MARK: HealthKit

    private var healthKitSection: some View {
        Section {
            if sync.isHealthDataAvailable() {
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Image(systemName: "heart.text.square.fill")
                            .font(.title3)
                            .foregroundStyle(.pink)
                        Text("Apple 健康同步")
                            .font(.subheadline.weight(.semibold))
                        Spacer()
                        if sync.isAuthorized {
                            Text("已授权").font(.caption2.weight(.bold))
                                .padding(.horizontal, 8).padding(.vertical, 3)
                                .background(EvilifeTheme.brandLight, in: Capsule())
                                .foregroundStyle(EvilifeTheme.brandDark)
                        }
                    }
                    Text("EviLife 只读取你逐类授权的步数、睡眠、静息心率与体重聚合值，并写入本服务健康档案。网页不能直接读取「健康」数据，自动同步必须由本机 HealthKit 授权。")
                        .font(.caption)
                        .foregroundStyle(EvilifeTheme.textSecondary)
                    if sync.isAuthorized {
                        Button {
                            Task { await syncNow() }
                        } label: {
                            HStack {
                                if sync.syncing {
                                    ProgressView().controlSize(.small)
                                    Text("正在同步…").font(.footnote)
                                } else {
                                    Text("同步最近 30 天数据").frame(maxWidth: .infinity)
                                }
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.pink)
                        .disabled(sync.syncing)
                        if let lastSync = sync.lastSyncAt {
                            Text("上次同步：\(lastSync.formatted(date: .abbreviated, time: .shortened))，新增 \(sync.lastAccepted) 条、跳过 \(sync.lastSkipped) 条")
                                .font(.caption2)
                                .foregroundStyle(EvilifeTheme.textTertiary)
                        }
                    } else {
                        Button {
                            Task { await authorize() }
                        } label: {
                            Text("授权 HealthKit").frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.pink)
                    }
                    if let error = sync.lastError ?? errorMessage.nilIfEmpty {
                        Text(error).font(.caption).foregroundStyle(EvilifeTheme.riskRefused)
                    }
                }
            } else {
                Text("当前设备不支持 HealthKit。你仍可以在「今日」手动记录，或在网页端导入 Apple 健康 XML。")
                    .font(.footnote)
                    .foregroundStyle(EvilifeTheme.textSecondary)
            }
        } header: {
            Text("数据同步")
        }
    }

    private func authorize() async {
        do {
            try await sync.requestAccess()
        } catch {
            sync.lastError = error.localizedDescription
        }
    }

    private func syncNow() async {
        do {
            _ = try await sync.sync(days: 30)
        } catch {
            sync.lastError = error.localizedDescription
        }
    }

    // MARK: Profile analysis

    private var profileSection: some View {
        Section {
            if analyzing {
                HStack { Spacer(); ProgressView("正在分析健康档案…"); Spacer() }
            } else if let profile {
                Text("来源：\(profile.source == "ai" ? "AI 分析" : "确定性规则")")
                    .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                ForEach(profile.cards.indices, id: \.self) { index in
                    let card = profile.cards[index]
                    VStack(alignment: .leading, spacing: 6) {
                        Text(card.title).font(.subheadline.weight(.semibold))
                        Text(card.preview).font(.footnote)
                        ForEach(card.details, id: \.self) { detail in
                            if let label = detail["label"], let value = detail["value"] {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(label).font(.caption2.weight(.semibold)).foregroundStyle(EvilifeTheme.textTertiary)
                                    Text(value).font(.caption).fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                    }
                    .padding(.vertical, 2)
                }
            } else {
                Button {
                    Task { await analyze() }
                } label: {
                    HStack {
                        Image(systemName: "chart.line.uptrend.xyaxis").foregroundStyle(EvilifeTheme.brand)
                        Text("分析我的健康档案")
                        Spacer()
                        Image(systemName: "chevron.right").font(.caption).foregroundStyle(EvilifeTheme.textTertiary)
                    }
                }
            }
        } header: {
            Text("健康档案分析")
        } footer: {
            Text("基于你已记录/同步的步数、睡眠、体重、静息心率等客观数据；自由文本备注不会发送给 AI。")
        }
    }

    private func analyze() async {
        analyzing = true
        defer { analyzing = false }
        do {
            profile = try await API.analyzeProfile()
            errorMessage = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    // MARK: Connectors

    private var connectorsSection: some View {
        Section("数据连接器") {
            if connectors.isEmpty {
                Text("加载中…").font(.footnote).foregroundStyle(EvilifeTheme.textTertiary)
            }
            ForEach(connectors) { connector in
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(connector.label).font(.subheadline.weight(.medium))
                        Spacer()
                        statusBadge(connector.status)
                    }
                    Text(connector.authorization)
                        .font(.caption).foregroundStyle(EvilifeTheme.textSecondary)
                    Text("支持：\(connector.supported_kinds.map(observationKindLabel).joined(separator: "、"))")
                        .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                }
            }
        }
    }

    @ViewBuilder
    private func statusBadge(_ status: String) -> some View {
        let (label, color): (String, Color) = {
            switch status {
            case "available": return ("可用", EvilifeTheme.supported)
            case "requires_credentials": return ("需凭据", EvilifeTheme.partly)
            default: return ("需原生桥接", EvilifeTheme.insufficient)
            }
        }()
        Text(label).font(.caption2.weight(.bold))
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(color.opacity(0.12), in: Capsule())
            .foregroundStyle(color)
    }

    private var disclaimerSection: some View {
        Section {
            Text(AppConfig.medicalDisclaimer)
                .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
        }
    }

    private func loadConnectors() async {
        connectors = (try? await API.connectors()) ?? []
    }
}

private extension String {
    var nilIfEmpty: String? { isEmpty ? nil : self }
}

#Preview {
    HealthView()
}
