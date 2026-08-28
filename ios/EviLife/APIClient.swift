import Foundation

enum APIRequestError: LocalizedError {
    case http(Int, String)
    case network(String)
    case decoding(String)

    var errorDescription: String? {
        switch self {
        case .http(let code, let detail):
            return "服务器错误 \(code)：\(detail)"
        case .network(let message):
            return "网络错误：\(message)"
        case .decoding(let message):
            return "数据解析失败：\(message)"
        }
    }
}

/// Session cookie is managed by URLSession's shared cookie storage
/// (`evilife_session`), mirroring the web client's cookie auth.
final class APIClient {
    static let shared = APIClient()

    private let session: URLSession

    init() {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 60
        configuration.timeoutIntervalForResource = 300
        configuration.httpCookieAcceptPolicy = .always
        configuration.httpShouldSetCookies = true
        session = URLSession(configuration: configuration)
    }

    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        return decoder
    }()

    static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        return encoder
    }()

    // MARK: Core request

    func request(
        _ path: String,
        method: String = "GET",
        body: Data? = nil,
        contentType: String? = nil
    ) async throws -> Data {
        guard let url = URL(string: AppConfig.baseURL + path) else {
            throw APIRequestError.network("无效的服务器地址：\(AppConfig.baseURL)")
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = body
        if let contentType { request.setValue(contentType, forHTTPHeaderField: "Content-Type") }
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIRequestError.network(error.localizedDescription)
        }
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw APIRequestError.http(http.statusCode, Self.errorDetail(from: data) ?? "请求未通过服务器校验")
        }
        return data
    }

    static func errorDetail(from data: Data) -> String? {
        if let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let detail = dict["detail"] as? String { return detail }
            if let details = dict["detail"] as? [[String: Any]] {
                let messages = details.compactMap { $0["msg"] as? String }
                return messages.isEmpty ? nil : messages.joined(separator: "；")
            }
            if let error = dict["error"] as? [String: Any], let message = error["message"] as? String {
                return message
            }
        }
        return nil
    }

    func get(_ path: String) async throws -> Data {
        try await request(path, method: "GET")
    }

    func post(_ path: String, json: Encodable) async throws -> Data {
        let body = try APIClient.encoder.encode(json)
        return try await request(path, method: "POST", body: body, contentType: "application/json")
    }

    func post(_ path: String) async throws -> Data {
        try await request(path, method: "POST")
    }

    func delete(_ path: String) async throws -> Data {
        try await request(path, method: "DELETE")
    }

    func postMultipart(
        _ path: String,
        fields: [String: String],
        fileField: String? = nil,
        fileName: String? = nil,
        mimeType: String? = nil,
        fileData: Data? = nil
    ) async throws -> Data {
        let boundary = "evilife-\(UUID().uuidString)"
        var body = Data()
        for (key, value) in fields {
            body.append(Data("--\(boundary)\r\n".utf8))
            body.append(Data("Content-Disposition: form-data; name=\"\(key)\"\r\n\r\n".utf8))
            body.append(Data("\(value)\r\n".utf8))
        }
        if let fileField, let fileName, let mimeType, let fileData {
            body.append(Data("--\(boundary)\r\n".utf8))
            body.append(Data("Content-Disposition: form-data; name=\"\(fileField)\"; filename=\"\(fileName)\"\r\n".utf8))
            body.append(Data("Content-Type: \(mimeType)\r\n\r\n".utf8))
            body.append(fileData)
            body.append(Data("\r\n".utf8))
        }
        body.append(Data("--\(boundary)--\r\n".utf8))
        return try await request(
            path, method: "POST", body: body,
            contentType: "multipart/form-data; boundary=\(boundary)")
    }

    static func decode<T: Decodable>(_ data: Data) throws -> T {
        try decoder.decode(T.self, from: data)
    }

    static func decode<T: Decodable>(_ type: T.Type, _ data: Data) throws -> T {
        try decoder.decode(type, from: data)
    }
}
