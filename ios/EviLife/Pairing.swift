import SwiftUI
import UIKit
import VisionKit

/// 原生二维码扫描（iOS 17 DataScannerViewController，无需额外权限描述之外的处理）。
struct QRScannerView: UIViewControllerRepresentable {
    var onScan: (String) -> Void
    @Environment(\.dismiss) private var dismiss

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let controller = DataScannerViewController(
            recognizedDataTypes: [.barcode(symbologies: [.qr])],
            qualityLevel: .balanced,
            recognizesMultipleItems: false,
            isHighFrameRateTrackingEnabled: false,
            isPinchToZoomEnabled: true,
            isGuidanceEnabled: true,
            isHighlightingEnabled: true)
        controller.delegate = context.coordinator
        try? controller.startScanning()
        return controller
    }

    func updateUIViewController(_ uiViewController: DataScannerViewController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        let parent: QRScannerView
        var handled = false

        init(_ parent: QRScannerView) { self.parent = parent }

        private func accept(_ value: String) {
            guard !handled else { return }
            handled = true
            parent.onScan(value)
        }

        func dataScanner(
            _ dataScanner: DataScannerViewController,
            didAdd addedItems: [RecognizedItem],
            allItems: [RecognizedItem]
        ) {
            for item in addedItems {
                if case .barcode(let barcode) = item,
                   let value = barcode.payloadStringValue {
                    accept(value)
                    return
                }
            }
        }

        func dataScanner(
            _ dataScanner: DataScannerViewController,
            didTapOn item: RecognizedItem
        ) {
            if case .barcode(let barcode) = item,
               let value = barcode.payloadStringValue {
                accept(value)
            }
        }
    }
}

// MARK: - 跨账号传输目标（持久化）

struct TransferLink: Codable {
    let token: String
    let targetEmail: String
    let targetName: String
    let expiresAt: Date

    var isExpired: Bool { expiresAt < Date() }
}

enum TransferLinkStore {
    private static let key = "evilife_transfer_link"

    static func save(_ link: TransferLink?) {
        guard let link else {
            UserDefaults.standard.removeObject(forKey: key)
            return
        }
        if let data = try? JSONEncoder().encode(link) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }

    static func load() -> TransferLink? {
        guard let data = UserDefaults.standard.data(forKey: key),
              let link = try? JSONDecoder().decode(TransferLink.self, from: data),
              !link.isExpired else {
            save(nil)
            return nil
        }
        return link
    }
}

/// 解析扫码内容：EviLife 配对 JSON / pairing_url JSON / URL 参数 / 原始配对码。
struct PairingPayload {
    let code: String?
    let baseURL: String?
    /// 网页端自定义格式：{"pairing_url": "http://host/api/v1/health-pairing/"}
    let pairingURL: String?
}

enum PairingParser {
    static func parse(_ raw: String) -> PairingPayload? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }

        // 0. JSON 携带 pairing_url：{"pairing_url":"http://…/health-pairing/"}
        if let data = trimmed.data(using: .utf8),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let pairingURL = json["pairing_url"] as? String,
           !pairingURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return PairingPayload(
                code: nil,
                baseURL: nil,
                pairingURL: pairingURL.trimmingCharacters(in: .whitespacesAndNewlines))
        }

        // 1. JSON：{"type":"evilife-pairing","base_url":"…","code":"ABC123"}
        if let data = trimmed.data(using: .utf8),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let rawCode = json["code"] as? String {
            let code = normalize(rawCode)
            if !code.isEmpty {
                return PairingPayload(
                    code: code,
                    baseURL: (json["base_url"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines),
                    pairingURL: nil)
            }
        }

        // 2. URL：https://host/…?code=XXX 或 evilife://pair?code=XXX
        if let url = URL(string: trimmed),
           let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
           let rawCode = components.queryItems?.first(where: { $0.name == "code" })?.value {
            let code = normalize(rawCode)
            if !code.isEmpty {
                return PairingPayload(code: code, baseURL: baseOf(components), pairingURL: nil)
            }
        }

        // 3. URL：最后一段路径形似配对码（如 https://host/pair/TDCDV8）
        if let url = URL(string: trimmed), url.scheme != nil, url.host != nil {
            let last = normalize(url.lastPathComponent)
            if (4...16).contains(last.count) {
                var base: String?
                if let scheme = url.scheme, let host = url.host {
                    base = "\(scheme)://\(host)"
                    if let port = url.port { base! += ":\(port)" }
                }
                return PairingPayload(code: last, baseURL: base, pairingURL: nil)
            }
        }

        // 4. 原始配对码（4–16 位字母数字）
        let cleaned = normalize(trimmed)
        if (4...16).contains(cleaned.count) {
            return PairingPayload(code: cleaned, baseURL: nil, pairingURL: nil)
        }
        return nil
    }

    private static func normalize(_ value: String) -> String {
        value.uppercased().filter { $0.isLetter || $0.isNumber }
    }

    private static func baseOf(_ components: URLComponents) -> String? {
        guard let scheme = components.scheme, let host = components.host else { return nil }
        var base = "\(scheme)://\(host)"
        if let port = components.port { base += ":\(port)" }
        return base
    }
}

// MARK: - 网页端 pairing_url 协议的客户端与持久化

struct WebSyncLink: Codable {
    let token: String
    let dataURL: String
    let savedAt: Date
}

enum WebSyncLinkStore {
    private static let key = "evilife_websync_link"

    static func save(_ link: WebSyncLink?) {
        guard let link else {
            UserDefaults.standard.removeObject(forKey: key)
            return
        }
        if let data = try? JSONEncoder().encode(link) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }

    static func load() -> WebSyncLink? {
        guard let data = UserDefaults.standard.data(forKey: key),
              let link = try? JSONDecoder().decode(WebSyncLink.self, from: data) else { return nil }
        return link
    }
}

enum WebSyncClient {
    /// POST {pairing_url}：登记设备，返回 token 与 data_url。
    static func pair(url: String) async throws -> (token: String, dataURL: String) {
        struct Body: Encodable {
            let app: String
            let device_name: String
            let consent_receipt: String
            let capabilities: [String]
        }
        let body = Body(
            app: "evilife-ios",
            device_name: UIDevice.current.name,
            consent_receipt: "healthkit-consent-\(UUID().uuidString)",
            capabilities: ["healthkit", "apple_watch"])

        var request = URLRequest(url: URL(string: url)!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        request.timeoutInterval = 30

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw APIRequestError.http(
                (response as? HTTPURLResponse)?.statusCode ?? -1,
                APIClient.errorDetail(from: data) ?? "网页端配对失败")
        }
        struct Reply: Decodable {
            let token: String
            let data_url: String?
        }
        let reply = try JSONDecoder().decode(Reply.self, from: data)
        guard let dataURL = reply.data_url, !dataURL.isEmpty else {
            throw APIRequestError.network("网页端响应缺少 data_url")
        }
        return (reply.token, dataURL)
    }

    /// POST {data_url}：上传聚合健康数据。
    static func upload(
        dataURL: String,
        token: String,
        observations: [ConnectorObservation]
    ) async throws -> (accepted: Int, total: Int) {
        struct Body: Encodable {
            let pairing_token: String
            let observations: [ConnectorObservation]
        }
        let body = Body(pairing_token: token, observations: observations)

        var request = URLRequest(url: URL(string: dataURL)!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        request.timeoutInterval = 60

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw APIRequestError.http(
                (response as? HTTPURLResponse)?.statusCode ?? -1,
                APIClient.errorDetail(from: data) ?? "上传失败")
        }
        struct Reply: Decodable {
            let accepted: Int?
            let total: Int?
        }
        let reply = try JSONDecoder().decode(Reply.self, from: data)
        return (reply.accepted ?? 0, reply.total ?? reply.accepted ?? 0)
    }
}
