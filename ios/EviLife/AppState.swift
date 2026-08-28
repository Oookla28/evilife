import Foundation

@MainActor
final class AppState: ObservableObject {
    @Published var user: PublicUser?
    @Published var bootstrapped = false
    @Published var busy = false
    @Published var toast: String?

    var isLoggedIn: Bool { user != nil }

    func bootstrap() async {
        do {
            user = try await API.me()
        } catch {
            user = nil // Guest mode: backend still accepts anonymous requests.
        }
        bootstrapped = true
    }

    func login(email: String, password: String) async throws {
        user = try await API.login(LoginInput(email: email, password: password))
    }

    func register(email: String, password: String, name: String) async throws {
        user = try await API.register(RegisterInput(email: email, password: password, display_name: name))
    }

    func logout() async {
        try? await API.logout()
        user = nil
        showToast("已退出登录")
    }

    func showToast(_ message: String) {
        toast = message
        Task { [weak self] in
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            if self?.toast == message { self?.toast = nil }
        }
    }
}
