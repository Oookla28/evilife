import Foundation
import Darwin

enum AppConfig {
    /// 默认后端：本机 FastAPI。优先级：启动探测结果 > 应用内手动设置 >
    /// Info.plist 的 EvilifeAPIBaseURL > 候选列表第一条。
    /// 开发默认端口 8000（FastAPI 默认监听）。
    static let loopbackFallback = "http://127.0.0.1:8000"

    /// 动态发现 CoreDevice USB 隧道：设备侧地址是 fdXX:…::1，Mac 侧是同前缀的 ::2。
    /// 隧道前缀每次重连都会变，因此不能写死，必须运行时枚举自己的 utun 接口。
    static func usbTunnelHostCandidates(port: Int = 8000) -> [String] {
        var candidates: [String] = []
        var ifaddrPtr: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&ifaddrPtr) == 0, let first = ifaddrPtr else { return candidates }
        defer { freeifaddrs(first) }
        var cursor: UnsafeMutablePointer<ifaddrs>? = first
        while let current = cursor {
            cursor = current.pointee.ifa_next
            guard let addr = current.pointee.ifa_addr,
                  addr.pointee.sa_family == UInt8(AF_INET6),
                  let namePtr = current.pointee.ifa_name else { continue }
            let interface = String(cString: namePtr)
            guard interface.hasPrefix("utun") else { continue }
            var hostname = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            var storage = addr.pointee // sockaddr
            let length = socklen_t(storage.sa_len)
            let result = withUnsafePointer(to: &storage) { ptr in
                getnameinfo(ptr, length, &hostname,
                            socklen_t(hostname.count), nil, 0, NI_NUMERICHOST)
            }
            guard result == 0 else { continue }
            let ip = String(cString: hostname)
            guard ip.hasPrefix("fd") else { continue }
            guard let lastColon = ip.lastIndex(of: ":") else { continue }
            let host = "\(ip[..<lastColon])::2"
            let candidate = "http://[\(host)]:\(port)"
            // 自己以 ::1 结尾的接口大概率就是 CoreDevice 隧道，优先探测
            if ip.hasSuffix("::1") {
                candidates.insert(candidate, at: 0)
            } else {
                candidates.append(candidate)
            }
        }
        return candidates
    }

    /// 启动时按顺序探测，取第一个 /api/v1/health 返回 200 的地址：
    /// 1. USB 隧道（动态发现，真机有线直连 Mac）
    /// 2. 局域网候选（队友后端 172.20.10.10、本机热点网段等）
    /// 3. 回环（模拟器）
    static var probeCandidates: [String] {
        usbTunnelHostCandidates() + [
            "http://10.43.15.30:8010",
            "http://172.20.10.14:8010",
            "http://172.20.10.10:8010",
            "http://172.19.55.237:8010",
            "http://192.168.43.5:8000",
            loopbackFallback,
        ]
    }

    static var baseURL: String {
        if let resolved = UserDefaults.standard.string(forKey: "evilife_resolved_url")?.trimmed,
           !resolved.isEmpty { return resolved }
        if let manual = UserDefaults.standard.string(forKey: "evilife_base_url")?.trimmed,
           !manual.isEmpty { return manual }
        if let plistValue = (Bundle.main.object(forInfoDictionaryKey: "EvilifeAPIBaseURL") as? String)?.trimmed,
           !plistValue.isEmpty { return plistValue }
        return probeCandidates.first ?? loopbackFallback
    }

    /// 启动时调用：验证手动地址，失败则按候选列表探测并缓存可用地址。
    static func probe() async {
        if let manual = UserDefaults.standard.string(forKey: "evilife_base_url")?.trimmed,
           !manual.isEmpty {
            if await healthOK(manual) {
                UserDefaults.standard.set(manual, forKey: "evilife_resolved_url")
                return
            }
        }
        for candidate in probeCandidates {
            if await healthOK(candidate) {
                UserDefaults.standard.set(candidate, forKey: "evilife_resolved_url")
                return
            }
        }
    }

    private static func healthOK(_ url: String) async -> Bool {
        guard let healthURL = URL(string: url + "/api/v1/health") else { return false }
        var request = URLRequest(url: healthURL)
        request.timeoutInterval = 2.5
        request.cachePolicy = .reloadIgnoringLocalCacheData
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    static func setBaseURL(_ url: String) {
        var cleaned = url.trimmingCharacters(in: .whitespacesAndNewlines)
        while cleaned.hasSuffix("/") { cleaned.removeLast() }
        UserDefaults.standard.set(cleaned, forKey: "evilife_base_url")
        UserDefaults.standard.removeObject(forKey: "evilife_resolved_url")
    }

    static let sessionCookieName = "evilife_session"

    static let appName = "EviLife"
    static let medicalDisclaimer = "EviLife 提供循证健康信息，不构成诊断或治疗建议。涉及用药、剂量、停药或紧急情况请咨询医生；危急时立即联系急救。"
}

private extension String {
    var trimmed: String { trimmingCharacters(in: .whitespacesAndNewlines) }
}
