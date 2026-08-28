import SwiftUI

@main
struct EviLifeApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(appState)
                .task {
                    await AppConfig.probe()
                    await appState.bootstrap()
                }
                .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
                    Task {
                        await AppConfig.probe()
                        await appState.bootstrap()
                    }
                }
        }
    }
}
