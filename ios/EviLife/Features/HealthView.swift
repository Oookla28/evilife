import SwiftUI
import HealthKitUI
import UniformTypeIdentifiers

struct HealthView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var sync = HealthKitSyncService()
    @State private var profile: ProfileAnalysisResponse?
    @State private var analyzing = false
    @State private var errorMessage = ""
    @State private var showReports = false
    @State private var showSettings = false

    @State private var showScanner = false
    @State private var pairingBusy = false
    @State private var pairingMessage = ""
    @State private var pairingError = ""
    @State private var manualCode = ""
    @State private var pendingPayload: PairingPayload?
    @State private var showPairingChoice = false
    @State private var transferring = false
    @State private var webSyncing = false

    @State private var syncDays = 30
    @State private var syncedStats: [String: Int] = [:]
    @State private var showXMLImporter = false
    @State private var importing = false
    @State private var importJob: AppleHealthImportJob?
    /// 每次 +1 触发一次 healthDataAccessRequest 授权弹窗
    @State private var healthAccessNonce = 0

    var body: some View {
        NavigationStack {
            List {
                profileSection
                healthKitSection
                pairingSection
                importSection
            }
            .listStyle(.insetGrouped)
            .navigationTitle("健康")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showSettings = true
                    } label: {
                        Image(systemName: "gearshape")
                    }
                    .accessibilityLabel("设置")
                }
            }
            .task {
                await loadSyncedStats()
                await sync.refreshAccessState()
            }
            .onAppear {
                Task { await sync.refreshAccessState() }
            }
            .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
                Task { await sync.refreshAccessState() }
            }
            .sheet(isPresented: $showScanner) {
                NavigationStack {
                    ZStack {
                        QRScannerView { raw in
                            handleScan(raw)
                        }
                        .ignoresSafeArea()
                        VStack {
                            Spacer()
                            Text("扫描网页端二维码")
                                .font(.footnote.weight(.medium))
                                .padding(.horizontal, 14).padding(.vertical, 8)
                                .background(.regularMaterial, in: Capsule())
                                .padding(.bottom, 40)
                        }
                    }
                    .navigationTitle("扫描二维码")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("取消") { showScanner = false }
                        }
                    }
                }
            }
            .sheet(isPresented: $showReports) { ReportsView() }
            .sheet(isPresented: $showSettings) { SettingsView() }
            .fileImporter(
                isPresented: $showXMLImporter,
                allowedContentTypes: [.xml, .data],
                allowsMultipleSelection: false
            ) { result in
                Task {
                    do {
                        guard let url = try result.get().first else { return }
                        await runXMLImport(url)
                    } catch {
                        importJob = AppleHealthImportJob(
                            id: "", status: "failed", processed_records: 0, summary: nil,
                            error: error.localizedDescription)
                    }
                }
            }
            .healthAccessRequestCompat(sync: sync, trigger: $healthAccessNonce)
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
                    if let user = appState.user {
                        Text(user.email)
                            .font(.subheadline.weight(.medium))
                            .lineLimit(1)
                    } else {
                        Text("尚未连接")
                            .font(.subheadline)
                            .foregroundStyle(EvilifeTheme.textSecondary)
                    }
                    Spacer()
                    if appState.user != nil {
                        Text("已连接").font(.caption2.weight(.bold))
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(EvilifeTheme.brandLight, in: Capsule())
                            .foregroundStyle(EvilifeTheme.brandDark)
                    }
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
                    Text(appState.user != nil ? "重新连接" : "连接")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(EvilifeTheme.brand)
                .disabled(pairingBusy)

                DisclosureGroup("输入配对码") {
                    HStack(spacing: 8) {
                        TextField("配对码", text: $manualCode)
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
                            pendingPayload = PairingPayload(code: code, baseURL: nil, pairingURL: nil, token: nil, connectorID: nil)
                            showPairingChoice = true
                        }
                        .disabled(pairingBusy || manualCode.uppercased().filter { $0.isLetter || $0.isNumber }.count < 4)
                    }
                }
                .font(.footnote)

                transferSection
                webSyncSection
            }
        } header: {
            Text("网页同步")
        } footer: {
            Text("配对码 5 分钟有效。仅扫描可信二维码。")
        }
        .confirmationDialog("选择配对方式", isPresented: $showPairingChoice, titleVisibility: .visible) {
            Button("绑定并登录") {
                if let payload = pendingPayload {
                    Task { await claim(code: payload.code ?? "", fallbackBase: payload.baseURL, mode: "login") }
                }
            }
            Button("仅传输数据") {
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
                        .foregroundStyle(EvilifeTheme.brand)
                    Text("网页端已连接")
                        .font(.footnote.weight(.medium))
                        .lineLimit(1)
                }
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
                        Label("同步", systemImage: "icloud.and.arrow.up.fill")
                            .font(.footnote.weight(.medium))
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(EvilifeTheme.brand)
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
            pairingMessage = "已同步 \(result.accepted) 条"
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
            pairingMessage = "已连接，正在同步…"
            let observations = try await sync.buildObservations(days: 30)
            let result = try await WebSyncClient.upload(
                dataURL: link.dataURL, token: link.token, observations: observations)
            pairingMessage = "已同步 \(result.accepted) 条"
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
                    Text("传输到 \(link.targetEmail)")
                        .font(.footnote.weight(.medium))
                }
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
                        Label("传输", systemImage: "arrow.right.circle.fill")
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
            pairingMessage = "已传输 \(response.accepted) 条"
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
            pairingError = "无法识别二维码：\(preview)"
            return
        }
        // 团队协议：{"pairing_url": "…", "token": "…", "connector_id": "…"} → 直接配对并上传
        if let pairingURL = payload.pairingURL {
            if let token = payload.token, !token.isEmpty {
                Task { await pairWithTeamProtocol(url: pairingURL, token: token, connectorID: payload.connectorID ?? "apple_healthkit") }
            } else {
                Task { await pairWithWeb(pairingURL) }
            }
            return
        }
        pendingPayload = payload
        showPairingChoice = true
    }

    /// 团队官方配对协议：扫码 → 构建观测 → POST pairing_url → 网页端状态变「已配对」。
    private func pairWithTeamProtocol(url: String, token: String, connectorID: String) async {
        pairingBusy = true
        defer { pairingBusy = false }
        do {
            pairingError = ""
            pairingMessage = "正在同步…"
            let observations = try await sync.buildObservations(days: syncDays)
            var result: (accepted: Int, skipped: Int)
            do {
                result = try await WebSyncClient.completePairing(
                    pairingURL: url, token: token, connectorID: connectorID,
                    observations: observations)
            } catch {
                // 二维码里的地址手机不可达（如 127.0.0.1）时，改用当前可用后端 + 原路径重试
                guard let fallback = rewrittenPairingURL(url), fallback != url else { throw error }
                result = try await WebSyncClient.completePairing(
                    pairingURL: fallback, token: token, connectorID: connectorID,
                    observations: observations)
            }
            pairingMessage = "已连接 · 新增 \(result.accepted) 条"
            await loadSyncedStats()
        } catch {
            pairingError = error.localizedDescription
        }
    }

    /// 把 127.0.0.1/localhost 的 pairing_url 改写成当前可用后端地址（路径不变）。
    private func rewrittenPairingURL(_ original: String) -> String? {
        guard let components = URLComponents(string: original),
              let host = components.host,
              (host == "127.0.0.1" || host == "localhost"),
              let base = URLComponents(string: AppConfig.baseURL),
              let baseHost = base.host else { return nil }
        var copy = components
        copy.scheme = base.scheme
        copy.host = baseHost
        copy.port = base.port
        return copy.string
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
            pairingMessage = "已连接 \(target.email) · 24 小时有效"
            pairingError = ""
        } else if let user = response.user {
            appState.user = user
            pairingMessage = "已绑定 \(user.email)"
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
                            .foregroundStyle(EvilifeTheme.brand)
                        Text("步数 · 睡眠 · 心率 · 体重")
                            .font(.subheadline)
                            .foregroundStyle(EvilifeTheme.textSecondary)
                        Spacer()
                        if sync.isAuthorized {
                            Text("已授权").font(.caption2.weight(.bold))
                                .padding(.horizontal, 8).padding(.vertical, 3)
                                .background(EvilifeTheme.brandLight, in: Capsule())
                            .foregroundStyle(EvilifeTheme.brandDark)
                        }
                    }
                    if sync.isAuthorized {
                        HStack(spacing: 12) {
                            Menu {
                                Picker("同步范围", selection: $syncDays) {
                                    Text("最近 7 天").tag(7)
                                    Text("最近 30 天").tag(30)
                                    Text("最近 90 天").tag(90)
                                }
                            } label: {
                                Text("\(syncDays) 天")
                                .font(.footnote.weight(.medium))
                                .foregroundStyle(EvilifeTheme.brandDark)
                            }
                            Spacer()
                            if sync.accessRequested {
                                Button("权限") { openAppSettings() }
                                    .font(.footnote)
                            }
                        }
                        Button {
                            Task { await syncNow() }
                        } label: {
                            HStack {
                                if sync.syncing {
                                    ProgressView().controlSize(.small)
                                    Text("同步中…").font(.footnote)
                                } else {
                                    Text("同步").frame(maxWidth: .infinity)
                                }
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(EvilifeTheme.brand)
                        .disabled(sync.syncing)
                        if let lastSync = sync.lastSyncAt {
                            Text("\(lastSync.formatted(date: .abbreviated, time: .shortened)) · 新增 \(sync.lastAccepted)")
                                .font(.caption2)
                                .foregroundStyle(EvilifeTheme.textTertiary)
                        }
                    } else {
                        Button {
                            healthAccessNonce += 1
                        } label: {
                            Text("连接 Apple 健康").frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(EvilifeTheme.brand)
                    }
                    syncedStatsRow
                    if let error = sync.lastError ?? errorMessage.nilIfEmpty {
                        Text(error).font(.caption).foregroundStyle(EvilifeTheme.riskRefused)
                    }
                }
            } else {
                Text("此设备不支持 HealthKit")
                    .font(.footnote)
                    .foregroundStyle(EvilifeTheme.textSecondary)
            }
        } header: {
            Text("Apple 健康")
        }
    }

    @ViewBuilder
    private var syncedStatsRow: some View {
        let kinds = ["steps", "sleep_minutes", "resting_heart_rate", "weight_kg", "water_ml", "waist_cm"]
        let visible = kinds.filter { (syncedStats[$0] ?? 0) > 0 }
        if !visible.isEmpty {
            let total = visible.reduce(0) { $0 + (syncedStats[$1] ?? 0) }
            Label("已同步 \(total) 条", systemImage: "checkmark.circle")
                .font(.caption)
                .foregroundStyle(EvilifeTheme.textTertiary)
        }
    }

    private func openAppSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) {
            UIApplication.shared.open(url)
        }
    }

    private func syncNow() async {
        do {
            if !sync.accessRequested {
                healthAccessNonce += 1
                sync.lastError = "请在系统授权页逐类允许读取后，回来再点一次同步。"
                return
            }
            _ = try await sync.sync(days: syncDays)
            await loadSyncedStats()
        } catch {
            sync.lastError = error.localizedDescription
        }
    }

    private func loadSyncedStats() async {
        guard let records = try? await API.observations(limit: 5000) else { return }
        var stats: [String: Int] = [:]
        for record in records where record.connector_id == "apple_healthkit" {
            stats[record.kind, default: 0] += 1
        }
        syncedStats = stats
    }

    // MARK: Apple 健康 XML 导入

    private var importSection: some View {
        Section {
            Button {
                showReports = true
            } label: {
                Label("体检报告", systemImage: "doc.text")
            }
            if importing {
                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 8) {
                        ProgressView().controlSize(.small)
                        Text("导入中…").font(.footnote)
                    }
                    if let job = importJob, job.processed_records > 0 {
                        Text("已解析 \(job.processed_records) 条记录").font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                    }
                }
            } else if let summary = importJob?.summary {
                VStack(alignment: .leading, spacing: 6) {
                    Label("导入完成", systemImage: "checkmark.circle.fill")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(EvilifeTheme.supported)
                    Text("新增 \(summary.accepted) · 跳过 \(summary.skipped)")
                        .font(.footnote)
                    DisclosureGroup("详情") {
                        Text(summary.source_file)
                        if let from = summary.date_from, let to = summary.date_to {
                            Text("\(from) – \(to)")
                        }
                        if !summary.counts.isEmpty {
                            Text(summary.counts
                                .sorted { $0.value > $1.value }
                                .prefix(5)
                                .map { "\(observationKindLabel($0.key)) \($0.value) 天" }
                                .joined(separator: " · "))
                        }
                    }
                    .font(.caption2)
                    .foregroundStyle(EvilifeTheme.textSecondary)
                    Button("再次导入") { showXMLImporter = true }.font(.footnote)
                }
            } else if let error = importJob?.error {
                VStack(alignment: .leading, spacing: 6) {
                    Text("导入失败：\(error)").font(.footnote).foregroundStyle(EvilifeTheme.riskRefused)
                    Button("重试") { showXMLImporter = true }.font(.footnote)
                }
            } else {
                Button {
                    showXMLImporter = true
                } label: {
                    Label("导入历史数据", systemImage: "square.and.arrow.down.on.square")
                }
            }
        } header: {
            Text("更多")
        } footer: {
            Text("支持 Apple 健康 export.xml，最大 1 GB。")
        }
    }

    private func runXMLImport(_ url: URL) async {
        importing = true
        importJob = nil
        defer { importing = false }
        do {
            let accessing = url.startAccessingSecurityScopedResource()
            defer { if accessing { url.stopAccessingSecurityScopedResource() } }
            let data = try Data(contentsOf: url)
            var job = try await API.importAppleHealth(fileData: data, fileName: url.lastPathComponent)
            importJob = job
            for _ in 0..<40 { // 最多轮询 60 秒
                if job.status == "completed" || job.status == "failed" { break }
                try await Task.sleep(nanoseconds: 1_500_000_000)
                job = try await API.getAppleHealthImport(job.id)
                importJob = job
            }
            if job.status == "completed" {
                await loadSyncedStats()
            }
        } catch {
            importJob = AppleHealthImportJob(
                id: "", status: "failed", processed_records: 0, summary: nil,
                error: error.localizedDescription)
        }
    }

    // MARK: Profile analysis

    private var profileSection: some View {
        Section {
            if analyzing {
                HStack { Spacer(); ProgressView("分析中…"); Spacer() }
            } else if let profile {
                ForEach(profile.cards.indices, id: \.self) { index in
                    let card = profile.cards[index]
                    VStack(alignment: .leading, spacing: 6) {
                        Text(card.title).font(.subheadline.weight(.semibold))
                        Text(card.preview).font(.footnote)
                        if !card.details.isEmpty {
                            DisclosureGroup("详情") {
                                ForEach(card.details, id: \.self) { detail in
                                    if let label = detail["label"], let value = detail["value"] {
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(label).font(.caption2.weight(.semibold)).foregroundStyle(EvilifeTheme.textTertiary)
                                            Text(value).font(.caption).fixedSize(horizontal: false, vertical: true)
                                        }
                                    }
                                }
                            }
                            .font(.caption)
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
                        Text("生成洞察")
                        Spacer()
                        Image(systemName: "chevron.right").font(.caption).foregroundStyle(EvilifeTheme.textTertiary)
                    }
                }
            }
        } header: {
            Text("健康洞察")
        } footer: {
            Text("仅使用健康指标，不上传备注。")
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

}

private extension String {
    var nilIfEmpty: String? { isEmpty ? nil : self }
}

// MARK: - 系统授权请求修饰符（HealthKitUI，iOS 17+，避免旧 API 呈现问题）

private struct HealthAccessRequestModifier: ViewModifier {
    let sync: HealthKitSyncService
    @Binding var nonce: Int

    func body(content: Content) -> some View {
        content.healthDataAccessRequest(
            store: sync.storeInstance,
            shareTypes: [],
            readTypes: sync.healthReadTypes,
            trigger: nonce
        ) { result in
            Task { @MainActor in
                if case .failure(let error) = result {
                    sync.lastError = error.localizedDescription
                }
                await sync.refreshAccessState()
            }
        }
    }
}

extension View {
    func healthAccessRequestCompat(sync: HealthKitSyncService, trigger: Binding<Int>) -> some View {
        modifier(HealthAccessRequestModifier(sync: sync, nonce: trigger))
    }
}

#Preview {
    HealthView()
}
