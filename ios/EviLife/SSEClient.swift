import Foundation

/// Minimal Server-Sent Events client over URLSession's async bytes stream.
final class SSEClient {
    private var cancelToken = false

    func connect(
        path: String,
        onEvent: @escaping (StreamEvent) -> Void
    ) async throws {
        cancelToken = false
        guard let url = URL(string: AppConfig.baseURL + path) else {
            throw APIRequestError.network("无效的事件流地址")
        }
        var request = URLRequest(url: url)
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")

        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let status = (response as? HTTPURLResponse)?.statusCode ?? -1
            throw APIRequestError.http(status, "事件流连接失败")
        }

        var buffer = ""
        for try await line in bytes.lines {
            if cancelToken { break }
            if line.isEmpty {
                if buffer.hasPrefix("data:") {
                    let payload = buffer.dropFirst(5).trimmingCharacters(in: .whitespaces)
                    if !payload.isEmpty,
                       let data = payload.data(using: .utf8),
                       let event = try? APIClient.decoder.decode(StreamEvent.self, from: data) {
                        onEvent(event)
                    }
                }
                buffer = ""
            } else if line.hasPrefix("data:") {
                buffer += line
            }
        }
    }

    func cancel() {
        cancelToken = true
    }
}
