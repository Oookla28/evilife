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
        }
    }
}
