import SwiftUI

@main
struct EviLifeApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(appState)
                .task {
#if targetEnvironment(simulator)
                    await HealthKitSyncService.seedSimulatorHealthDataIfRequested()
#endif
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
