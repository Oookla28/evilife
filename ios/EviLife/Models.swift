import Foundation

// MARK: - Flexible JSON (module props are `dict[str, Any]`)

enum JSONValue: Codable, Equatable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() { self = .null; return }
        if let value = try? container.decode(Bool.self) { self = .bool(value); return }
        if let value = try? container.decode(Double.self) { self = .number(value); return }
        if let value = try? container.decode(String.self) { self = .string(value); return }
        if let value = try? container.decode([JSONValue].self) { self = .array(value); return }
        if let value = try? container.decode([String: JSONValue].self) { self = .object(value); return }
        throw DecodingError.dataCorruptedError(
            in: container, debugDescription: "unsupported JSON value")
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }

    // Accessors
    var string: String? { if case .string(let value) = self { return value }; return nil }
    var double: Double? { if case .number(let value) = self { return value }; return nil }
    var int: Int? { double.map(Int.init) }
    var bool: Bool? { if case .bool(let value) = self { return value }; return nil }
    var array: [JSONValue]? { if case .array(let value) = self { return value }; return nil }
    var object: [String: JSONValue]? { if case .object(let value) = self { return value }; return nil }
    var stringArray: [String] { array?.compactMap(\.string) ?? [] }
    var stringInts: [Int] { array?.compactMap(\.int) ?? [] }
    var stringDoubles: [Double] { array?.compactMap(\.double) ?? [] }

    var isNull: Bool { if case .null = self { return true }; return false }

    var displayText: String {
        switch self {
        case .string(let value): return value
        case .number(let value): return value == value.rounded() ? String(Int(value)) : String(value)
        case .bool(let value): return value ? "true" : "false"
        case .null: return "—"
        case .array(let values): return values.map(\.displayText).joined(separator: "、")
        case .object: return "[对象]"
        }
    }

    subscript(key: String) -> JSONValue? { object?[key] }
}

// MARK: - Auth

struct PublicUser: Codable, Equatable {
    let id: String
    let email: String
    let display_name: String
    let subject_id: String
}

/// /device-pairing/claim 的响应：login 模式带 user，transfer 模式带 transfer_token + target。
struct PairingClaimResponse: Codable {
    let mode: String?
    let user: PublicUser?
    let transfer_token: String?
    let expires_in: Int?
    let target: PublicUser?
}

struct RegisterInput: Encodable {
    let email: String
    let password: String
    let display_name: String
}

struct LoginInput: Encodable {
    let email: String
    let password: String
}

// MARK: - Orchestrate / SSE

struct ModulePlanItem: Codable, Identifiable {
    let module_id: String
    let type: String
    let version: String?
    let priority: Double?
    let status: String
    let props: [String: JSONValue]
    var id: String { module_id }

    var prop: [String: JSONValue] { props }
}

struct ActionItem: Codable, Identifiable {
    let action_id: String
    let type: String
    let label: String
    let requires_confirmation: Bool
    let status: String
    let payload_preview: [String: JSONValue]?
    var id: String { action_id }
}

struct OrchestrateResponse: Codable {
    let request_id: String
    let session_id: String
    let run_id: String
    let intent: String?
    let risk_level: String?
    let gate_status: String
    let status: String
    let module_plan: [ModulePlanItem]
    let actions: [ActionItem]
    let mode: String?
    let route: String?
    let evidence_count: Int
    let support_evidence_count: Int
    let boundary_evidence_count: Int
    let timing_ms: [String: Double]
}

struct StreamEvent: Codable {
    let event_id: String
    let request_id: String
    let run_id: String
    let type: String
    let timestamp: String
    let payload: [String: JSONValue]?
}

// MARK: - Lifestyle

struct ObservationRecord: Codable, Identifiable {
    let id: String
    let kind: String
    let value: Double?
    let note: String?
    let source: String
    let observed_at: String
    let connector_id: String?
    let external_id: String?
}

struct ObservationCreate: Encodable {
    let kind: String
    let value: Double?
    let note: String?
    let source: String
    let observed_at: String?

    init(kind: String, value: Double? = nil, note: String? = nil,
         source: String = "self_report", observedAt: String? = nil) {
        self.kind = kind
        self.value = value
        self.note = note
        self.source = source
        self.observed_at = observedAt
    }
}

struct FastRecord: Codable, Identifiable {
    let id: String
    let start_at: String
    let end_at: String?
    let goal_hours: Double
    let status: String
}

struct MealItem: Codable, Identifiable {
    let id: String
    let name: String
    let portion: String
    let portion_grams: [Int]?
    let estimated_calories: [Int]
    let estimated_calories_center: Int?
    let confidence: String?
    let reference_basis: String?
    let uncertainty: String?
}

struct MealRecord: Codable, Identifiable {
    let id: String
    let action_id: String
    let created_at: String
    let items: [MealItem]?
    let estimated_total_calories: [Double]
    let estimated_total_calories_center: Double?
    let status: String
}

struct TodaySummary: Codable {
    let date: String
    let fasts: [FastRecord]
    let meals: [MealRecord]
    let observations: [ObservationRecord]
}

struct HealthConnector: Codable, Identifiable {
    let id: String
    let label: String
    let status: String
    let authorization: String
    let transport: String
    let docs_url: String
    let supported_kinds: [String]
}

struct ConnectorObservation: Encodable {
    let external_id: String
    let observation: ObservationCreate
}

struct ConnectorIngestRequest: Encodable {
    let consent_receipt: String
    let observations: [ConnectorObservation]
}

struct ConnectorIngestResponse: Codable {
    let connector_id: String
    let accepted: Int
    let skipped: Int
    let records: [ObservationRecord]
}

struct ProfileAnalysisCard: Codable {
    let tone: String
    let title: String
    let preview: String
    let details: [[String: String]]
}

struct ProfileAnalysisResponse: Codable {
    let source: String
    let cards: [ProfileAnalysisCard]
}

// MARK: - Apple 健康 XML 导入

struct AppleHealthImportSummary: Codable {
    let source_file: String
    let processed_records: Int
    let accepted: Int
    let skipped: Int
    let date_from: String?
    let date_to: String?
    let counts: [String: Int]
}

struct AppleHealthImportJob: Codable {
    let id: String
    let status: String // queued / running / completed / failed
    let processed_records: Int
    let summary: AppleHealthImportSummary?
    let error: String?
}

// MARK: - Reports

struct ReportItem: Codable, Identifiable {
    let name: String
    let value: String
    let unit: String
    let reference_range: String
    let flag: String
    var id: String { name + value + reference_range + flag }
}

struct ReportAnalysis: Codable {
    let report_id: String
    let file_name: String
    let source: String
    let summary: String
    let items: [ReportItem]
    let limitations: [String]
}

// MARK: - Conversations

struct ConversationMessage: Codable, Identifiable {
    let id: String
    let role: String
    let content: String?
    let file: [String: String]?
    let modulePlan: [ModulePlanItem]?
}

struct Conversation: Codable, Identifiable {
    let session_id: String
    let title: String
    let mode: String
    let messages: [ConversationMessage]
    let updated_at: String
    var id: String { session_id }
}

// MARK: - Date helpers

enum ISODate {
    static func now() -> String { ISO8601DateFormatter().string(from: Date()) }
    static func today() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "Asia/Shanghai")
        return formatter.string(from: Date())
    }
    /// 本地（Asia/Shanghai）今天的正午 ISO 时间：保证后端按 UTC 日期过滤时
    /// 与用户看到的本地日期一致（凌晨 0-8 点也不会错位到昨天）。
    static func localNoon() -> String {
        "\(today())T12:00:00+08:00"
    }
    static func parse(_ value: String) -> Date? {
        ISO8601DateFormatter().date(from: value)
            ?? ISO8601DateFormatter.withFractional.date(from: value)
    }
    static func localShort(_ value: String) -> String {
        guard let date = parse(value) else { return value }
        let formatter = DateFormatter()
        formatter.dateFormat = "MM-dd HH:mm"
        return formatter.string(from: date)
    }
    static func time(_ value: String) -> String {
        guard let date = parse(value) else { return value }
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: date)
    }
}

extension ISO8601DateFormatter {
    static let withFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()
}
