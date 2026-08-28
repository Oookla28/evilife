import Foundation

enum AppConfig {
    /// 默认后端：本机 FastAPI。优先级：启动探测结果 > 应用内手动设置 >
    /// Info.plist 的 EvilifeAPIBaseURL > 候选列表第一条。
    /// 8000 被本机其他进程占用，开发默认用 8010。
    static let loopbackFallback = "http://127.0.0.1:8010"

    /// 启动时按顺序探测，取第一个 /api/v1/health 返回 200 的地址：
    /// 1. USB 隧道（真机有线直连 Mac，Mac 侧地址 fd2f:e300:f785::2）
    /// 2. 局域网 Wi-Fi（Mac en0 地址）
    /// 3. 回环（模拟器）
    static var probeCandidates: [String] {
        [
            "http://[fd2f:e300:f785::2]:8010",
            "http://172.19.55.237:8010",
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
