import Foundation

/// Typed wrappers over the EviLife backend HTTP API (mirrors web `lib/api`).
enum API {

    // MARK: Auth

    static func register(_ input: RegisterInput) async throws -> PublicUser {
        try APIClient.decode(PublicUser.self, try await APIClient.shared.post("/api/v1/auth/register", json: input))
    }

    static func login(_ input: LoginInput) async throws -> PublicUser {
        try APIClient.decode(PublicUser.self, try await APIClient.shared.post("/api/v1/auth/login", json: input))
    }

    static func logout() async throws {
        _ = try await APIClient.shared.post("/api/v1/auth/logout")
    }

    static func me() async throws -> PublicUser {
        try APIClient.decode(PublicUser.self, try await APIClient.shared.get("/api/v1/auth/me"))
    }

    // MARK: Device pairing（扫码绑定 / 跨账号传输）

    static func claimDevicePairing(code: String, mode: String = "login") async throws -> PairingClaimResponse {
        struct Body: Encodable { let code: String; let mode: String }
        let data = try await APIClient.shared.post("/api/v1/device-pairing/claim", json: Body(code: code, mode: mode))
        return try APIClient.decoder.decode(PairingClaimResponse.self, from: data)
    }

    static func transferDeviceData(
        token: String,
        consentReceipt: String,
        observations: [ConnectorObservation]
    ) async throws -> ConnectorIngestResponse {
        struct Body: Encodable {
            let transfer_token: String
            let consent_receipt: String
            let observations: [ConnectorObservation]
        }
        let data = try await APIClient.shared.post(
            "/api/v1/device-pairing/transfer-data",
            json: Body(transfer_token: token, consent_receipt: consentReceipt, observations: observations))
        return try APIClient.decoder.decode(ConnectorIngestResponse.self, from: data)
    }

    // MARK: Orchestrate / SSE

    static func orchestrate(
        sessionId: String,
        mode: String = "auto",
        text: String?,
        image: Data? = nil,
        imageName: String? = nil,
        imageMime: String? = nil
    ) async throws -> OrchestrateResponse {
        var fields: [String: String] = ["session_id": sessionId, "mode": mode]
        if let text, !text.isEmpty { fields["text"] = text }
        let data = try await APIClient.shared.postMultipart(
            "/api/v1/orchestrate",
            fields: fields,
            fileField: image != nil ? "image" : nil,
            fileName: imageName,
            mimeType: imageMime,
            fileData: image
        )
        return try APIClient.decoder.decode(OrchestrateResponse.self, from: data)
    }

    static func streamEvents(runId: String, onEvent: @escaping (StreamEvent) -> Void) async throws {
        try await SSEClient().connect(path: "/api/v1/runs/\(runId)/events", onEvent: onEvent)
    }

    static func getRun(_ runId: String) async throws -> OrchestrateResponse {
        try APIClient.decoder.decode(
            OrchestrateResponse.self,
            from: try await APIClient.shared.get("/api/v1/runs/\(runId)"))
    }

    // MARK: Today / Fasting

    static func today(date: String) async throws -> TodaySummary {
        try APIClient.decoder.decode(
            TodaySummary.self,
            from: try await APIClient.shared.get("/api/v1/today?date=\(date)"))
    }

    static func activeFast() async throws -> FastRecord? {
        try APIClient.decoder.decode(
            FastRecord?.self,
            from: try await APIClient.shared.get("/api/v1/fasts/active"))
    }

    static func startFast(goalHours: Double) async throws -> FastRecord {
        struct Body: Encodable { let goal_hours: Double }
        return try APIClient.decoder.decode(
            FastRecord.self,
            from: try await APIClient.shared.post("/api/v1/fasts/start", json: Body(goal_hours: goalHours)))
    }

    static func endFast(_ id: String) async throws -> FastRecord {
        try APIClient.decoder.decode(
            FastRecord.self,
            from: try await APIClient.shared.post("/api/v1/fasts/\(id)/end"))
    }

    static func listFasts(limit: Int = 20) async throws -> [FastRecord] {
        try APIClient.decoder.decode(
            [FastRecord].self,
            from: try await APIClient.shared.get("/api/v1/fasts?limit=\(limit)"))
    }

    // MARK: Observations

    static func addObservation(_ input: ObservationCreate) async throws -> ObservationRecord {
        try APIClient.decoder.decode(
            ObservationRecord.self,
            from: try await APIClient.shared.post("/api/v1/observations", json: input))
    }

    static func addObservations(_ inputs: [ObservationCreate]) async throws -> [ObservationRecord] {
        struct Body: Encodable { let observations: [ObservationCreate] }
        return try APIClient.decoder.decode(
            [ObservationRecord].self,
            from: try await APIClient.shared.post("/api/v1/observations/batch", json: Body(observations: inputs)))
    }

    static func deleteObservation(_ id: String) async throws {
        _ = try await APIClient.shared.delete("/api/v1/observations/\(id)")
    }

    static func observations(kind: String? = nil, limit: Int = 5000) async throws -> [ObservationRecord] {
        var path = "/api/v1/observations?limit=\(limit)"
        if let kind { path += "&kind=\(kind)" }
        return try APIClient.decoder.decode(
            [ObservationRecord].self,
            from: try await APIClient.shared.get(path))
    }

    // MARK: Apple 健康 XML 导入（网页端迁移通道）

    static func importAppleHealth(fileData: Data, fileName: String) async throws -> AppleHealthImportJob {
        let data = try await APIClient.shared.postMultipart(
            "/api/v1/health-imports/apple",
            fields: [:],
            fileField: "export",
            fileName: fileName,
            mimeType: "text/xml",
            fileData: fileData)
        return try APIClient.decoder.decode(AppleHealthImportJob.self, from: data)
    }

    static func getAppleHealthImport(_ jobId: String) async throws -> AppleHealthImportJob {
        try APIClient.decoder.decode(
            AppleHealthImportJob.self,
            from: try await APIClient.shared.get("/api/v1/health-imports/apple/\(jobId)"))
    }

    // MARK: Health connectors

    static func connectors() async throws -> [HealthConnector] {
        try APIClient.decoder.decode(
            [HealthConnector].self,
            from: try await APIClient.shared.get("/api/v1/health-connectors"))
    }

    static func ingest(connectorId: String, consentReceipt: String, observations: [ConnectorObservation]) async throws -> ConnectorIngestResponse {
        let body = ConnectorIngestRequest(consent_receipt: consentReceipt, observations: observations)
        return try APIClient.decoder.decode(
            ConnectorIngestResponse.self,
            from: try await APIClient.shared.post("/api/v1/health-connectors/\(connectorId)/ingest", json: body))
    }

    // MARK: Profile analysis

    static func analyzeProfile() async throws -> ProfileAnalysisResponse {
        try APIClient.decoder.decode(
            ProfileAnalysisResponse.self,
            from: try await APIClient.shared.post("/api/v1/profile/analyze"))
    }

    // MARK: Reports

    static func analyzeReport(fileData: Data, fileName: String, mimeType: String) async throws -> ReportAnalysis {
        let data = try await APIClient.shared.postMultipart(
            "/api/v1/reports/analyze",
            fields: [:],
            fileField: "file",
            fileName: fileName,
            mimeType: mimeType,
            fileData: fileData)
        return try APIClient.decoder.decode(ReportAnalysis.self, from: data)
    }

    static func listReports(limit: Int = 50) async throws -> [[String: JSONValue]] {
        try APIClient.decoder.decode(
            [[String: JSONValue]].self,
            from: try await APIClient.shared.get("/api/v1/reports?limit=\(limit)"))
    }

    // MARK: Conversations

    static func conversations(limit: Int = 50) async throws -> [Conversation] {
        try APIClient.decoder.decode(
            [Conversation].self,
            from: try await APIClient.shared.get("/api/v1/conversations?limit=\(limit)"))
    }

    static func saveConversation(_ conversation: Conversation) async throws {
        struct Upsert: Encodable {
            let session_id: String
            let title: String
            let mode: String
            let messages: [ConversationMessage]
        }
        let body = Upsert(
            session_id: conversation.session_id,
            title: conversation.title,
            mode: conversation.mode,
            messages: conversation.messages)
        _ = try await APIClient.shared.request(
            "/api/v1/conversations/\(conversation.session_id)",
            method: "PUT",
            body: APIClient.encoder.encode(body),
            contentType: "application/json")
    }

    static func deleteConversation(_ id: String) async throws {
        _ = try await APIClient.shared.delete("/api/v1/conversations/\(id)")
    }
}
