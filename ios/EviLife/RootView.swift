import SwiftUI

struct RootView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        Group {
            if appState.bootstrapped {
                TabView {
                    ChatView()
                        .tabItem { Label("问答", systemImage: "bubble.left.and.bubble.right.fill") }
                    TodayView()
                        .tabItem { Label("今日", systemImage: "calendar") }
                    HealthView()
                        .tabItem { Label("健康", systemImage: "heart.fill") }
                    ReportsView()
                        .tabItem { Label("报告", systemImage: "doc.text.magnifyingglass") }
                    SettingsView()
                        .tabItem { Label("设置", systemImage: "gearshape.fill") }
                }
                .overlay(alignment: .top) {
                    if let toast = appState.toast {
                        Text(toast)
                            .font(.footnote.weight(.medium))
                            .padding(.horizontal, 14)
                            .padding(.vertical, 8)
                            .background(.regularMaterial, in: Capsule())
                            .padding(.top, 4)
                            .transition(.move(edge: .top).combined(with: .opacity))
                            .animation(.spring(duration: 0.3), value: appState.toast)
                    }
                }
            } else {
                ZStack {
                    EvilifeTheme.pageBg.ignoresSafeArea()
                    ProgressView("正在连接 EviLife…")
                }
            }
        }
    }
}

#Preview {
    RootView().environmentObject(AppState())
}
