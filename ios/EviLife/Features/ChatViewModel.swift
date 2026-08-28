import Foundation
import SwiftUI
import UIKit

@MainActor
final class ChatViewModel: ObservableObject {

    enum Role { case user, assistant }
    enum MessageStatus: Equatable {
        case waiting          // orchestrating
        case streaming        // SSE connected, modules pending
        case done
        case failed(String)
    }

    struct Message: Identifiable {
        let id = UUID()
        let role: Role
        var text: String?
        var imageData: Data?
        var modules: [ModulePlanItem] = []
        var status: MessageStatus = .waiting
        var route: String?
        var gateStatus: String?
        var evidenceTotal = 0
        var evidenceSupport = 0
        var evidenceBoundary = 0
        var runId: String?
        var timing: [String: Double] = [:]
    }

    @Published var messages: [Message] = []
    @Published var isSending = false
    @Published var mode: String = "auto"
    @Published var sessionId: String

    private var sseClient: SSEClient?

    init() {
        let stored = UserDefaults.standard.string(forKey: "evilife_chat_session")
        sessionId = stored ?? "s-ios-\(UUID().uuidString.prefix(12))"
        if stored == nil {
            UserDefaults.standard.set(sessionId, forKey: "evilife_chat_session")
        }
    }

    var modeLabel: String {
        switch mode {
        case "fast": return "快速"
        case "deep": return "深度"
        case "evaluation": return "评估"
        default: return "自动"
        }
    }

    // MARK: Send

    func send(text: String?, imageData: Data? = nil, imageName: String? = nil, imageMime: String? = nil) async {
        let trimmed = text?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard !isSending, (!trimmed.isEmpty || imageData != nil) else { return }
        isSending = true

        var userMessage = Message(role: .user, text: trimmed.isEmpty ? nil : trimmed, imageData: imageData)
        userMessage.status = .done
        messages.append(userMessage)

        var assistant = Message(role: .assistant, status: .waiting)
        let assistantIndex = messages.count
        messages.append(assistant)

        do {
            let response = try await API.orchestrate(
                sessionId: sessionId,
                mode: mode,
                text: trimmed.isEmpty ? nil : trimmed,
                image: imageData,
                imageName: imageName,
                imageMime: imageMime
            )
            messages[assistantIndex].runId = response.run_id
            messages[assistantIndex].gateStatus = response.gate_status
            messages[assistantIndex].timing = response.timing_ms
            if !response.module_plan.isEmpty {
                // Backend answers synchronously for most routes; render immediately.
                messages[assistantIndex].modules = response.module_plan
                messages[assistantIndex].evidenceTotal = response.evidence_count
                messages[assistantIndex].evidenceSupport = response.support_evidence_count
                messages[assistantIndex].evidenceBoundary = response.boundary_evidence_count
            }
            if let route = response.route {
                messages[assistantIndex].route = route
            }
            messages[assistantIndex].status = .streaming

            await streamRun(runId: response.run_id, assistantIndex: assistantIndex)
        } catch {
            messages[assistantIndex].status = .failed(error.localizedDescription)
        }

        isSending = false
        // Guests get 401 from the conversations API; failures are ignored.
        saveConversation()
    }

    private func streamRun(runId: String, assistantIndex: Int) async {
        let client = SSEClient()
        sseClient = client
        defer { sseClient = nil }
        do {
            try await client.connect(path: "/api/v1/runs/\(runId)/events") { [weak self] event in
                Task { @MainActor in
                    self?.handle(event, assistantIndex: assistantIndex)
                }
            }
            if case .streaming = messages[safe: assistantIndex]?.status {
                messages[assistantIndex].status = .done
            }
        } catch {
            // SSE stream failed — fall back to the stored run if we already have modules.
            if messages[safe: assistantIndex]?.modules.isEmpty ?? true {
                if let run = try? await API.getRun(runId) {
                    messages[assistantIndex].modules = run.module_plan
                }
                messages[assistantIndex].status = .done
            } else {
                messages[assistantIndex].status = .done
            }
        }
    }

    private func handle(_ event: StreamEvent, assistantIndex: Int) {
        guard messages.indices.contains(assistantIndex) else { return }
        switch event.type {
        case "run.started":
            messages[assistantIndex].status = .streaming
        case "route.selected":
            if let route = event.payload?["route"]?.string {
                messages[assistantIndex].route = route
            }
        case "evidence.snapshot":
            messages[assistantIndex].evidenceTotal = event.payload?["evidence_count"]?.int ?? messages[assistantIndex].evidenceTotal
            messages[assistantIndex].evidenceSupport = event.payload?["support_evidence_count"]?.int ?? messages[assistantIndex].evidenceSupport
            messages[assistantIndex].evidenceBoundary = event.payload?["boundary_evidence_count"]?.int ?? messages[assistantIndex].evidenceBoundary
        case "gate.completed":
            if let status = event.payload?["status"]?.string {
                messages[assistantIndex].gateStatus = status
            }
        case "module.ready":
            if let plan = event.payload?["module_plan"] {
                if let decoded = try? JSONDecoder().decode([ModulePlanItem].self, from: JSONSerialization.data(withJSONObject: plan.jsonObject ?? [])) {
                    messages[assistantIndex].modules = decoded
                }
            }
        case "run.completed", "run.failed":
            messages[assistantIndex].status = .done
        default:
            break
        }
    }

    // MARK: 直连大模型 API

    static let directSystemPrompt = """
    你是循证健康助手。回答前先判断问题是否属于医疗健康范围：
    非健康问题正常回答；健康问题应给出平衡、可核实的循证信息，
    不编造文献、剂量或诊断，不构成诊断或治疗建议；
    涉及停药、改药、剂量调整或紧急症状时，提醒用户咨询医生或及时就医。
    """

    func sendDirect(text: String, imageData: Data? = nil, imageMime: String? = nil) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !isSending, (!trimmed.isEmpty || imageData != nil) else { return }
        isSending = true

        var userMessage = Message(role: .user, text: trimmed.isEmpty ? nil : trimmed, imageData: imageData)
        userMessage.status = .done
        messages.append(userMessage)

        var assistant = Message(role: .assistant, status: .waiting)
        let assistantIndex = messages.count
        messages.append(assistant)

        do {
            let store = APIConfigStore.shared
            let reply: String
            if let imageData, let imageMime, store.visionEnabled {
                reply = try await DirectAPI.chatVision(
                    text: trimmed.isEmpty ? nil : trimmed,
                    imageData: imageData,
                    imageMime: imageMime,
                    base: store.visionBaseURL,
                    key: store.visionKey,
                    model: store.visionModel,
                    maxTokens: store.maxTokens)
            } else {
                reply = try await DirectAPI.chat(
                    messages: directHistory(),
                    base: store.baseURL,
                    key: store.apiKey,
                    model: store.model,
                    maxTokens: store.maxTokens,
                    reasoningEffort: store.isReasoningModel ? ["low", "medium", "high"][store.reasoningLevel] : nil)
            }
            messages[assistantIndex].text = reply
            messages[assistantIndex].status = .done
        } catch {
            messages[assistantIndex].status = .failed(error.localizedDescription)
        }

        isSending = false
    }

    private func directHistory() -> [DirectChatMessage] {
        var items: [DirectChatMessage] = [
            DirectChatMessage(role: "system", content: Self.directSystemPrompt)
        ]
        for message in messages.suffix(12) {
            guard let text = message.text,
                  !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  message.modules.isEmpty else { continue }
            items.append(DirectChatMessage(
                role: message.role == .user ? "user" : "assistant",
                content: text))
        }
        return items
    }

    // MARK: Conversation persistence

    func saveConversation() {
        guard !messages.isEmpty else { return }
        var items: [ConversationMessage] = []
        for message in messages {
            let content = message.text
            let modulePlan = message.modules.isEmpty ? nil : message.modules
            items.append(ConversationMessage(
                id: message.id.uuidString,
                role: message.role == .user ? "user" : "assistant",
                content: content,
                file: message.imageData != nil ? ["kind": "image"] : nil,
                modulePlan: modulePlan))
        }
        let title = messages.compactMap(\.text).first.map { String($0.prefix(24)) } ?? "新对话"
        let conversation = Conversation(
            session_id: sessionId,
            title: title,
            mode: "life",
            messages: items,
            updated_at: ISODate.now())
        Task {
            try? await API.saveConversation(conversation)
        }
    }

    func clear() {
        sseClient?.cancel()
        messages.removeAll()
        sessionId = "s-ios-\(UUID().uuidString.prefix(12))"
        UserDefaults.standard.set(sessionId, forKey: "evilife_chat_session")
    }

    func sendOption(_ value: String) {
        Task { await send(text: value) }
    }
}

private extension JSONValue {
    var jsonObject: Any? {
        switch self {
        case .string(let value): return value
        case .number(let value): return value
        case .bool(let value): return value
        case .object(let value): return value.mapValues { $0.jsonObject }
        case .array(let value): return value.map { $0.jsonObject }
        case .null: return NSNull()
        }
    }
}

extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
