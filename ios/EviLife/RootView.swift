import SwiftUI

struct RootView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        // 不阻塞启动：探测与登录在后台进行，界面立即可用（GPT/Claude 同款策略）
        TabView {
            ChatView()
                .tabItem { Label("问答", systemImage: "bubble.left.and.text.bubble.right") }
            TodayView()
                .tabItem { Label("今日", systemImage: "calendar") }
            HealthView()
                .tabItem { Label("健康", systemImage: "heart") }
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
    }
}

#Preview {
    RootView().environmentObject(AppState())
}
