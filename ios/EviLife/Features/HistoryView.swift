import SwiftUI

struct HistoryView: View {
    @EnvironmentObject var appState: AppState
    @State private var conversations: [Conversation] = []
    @State private var errorMessage = ""
    @State private var loading = false

    var body: some View {
        NavigationStack {
            List {
                if !appState.isLoggedIn {
                    Section {
                        Text("登录后可在多设备间同步问答历史；游客模式的对话只保存在本机。")
                            .font(.footnote).foregroundStyle(EvilifeTheme.textSecondary)
                    }
                }
                if !errorMessage.isEmpty {
                    Section {
                        Text(errorMessage).font(.footnote).foregroundStyle(EvilifeTheme.riskRefused)
                    }
                }
                Section("历史对话") {
                    if loading {
                        HStack { Spacer(); ProgressView(); Spacer() }
                    } else if conversations.isEmpty {
                        Text("暂无历史对话。").font(.footnote).foregroundStyle(EvilifeTheme.textTertiary)
                    }
                    ForEach(conversations) { conversation in
                        NavigationLink {
                            ConversationDetailView(conversation: conversation)
                        } label: {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(conversation.title).font(.subheadline)
                                Text("\(conversation.messages.count) 条消息 · \(ISODate.localShort(conversation.updated_at))")
                                    .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                            }
                        }
                        .swipeActions {
                            Button("删除", role: .destructive) {
                                Task { await delete(conversation) }
                            }
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("历史")
            .refreshable { await load() }
            .task { await load() }
        }
    }

    private func load() async {
        guard appState.isLoggedIn else { return }
        loading = true
        defer { loading = false }
        do {
            conversations = try await API.conversations()
            errorMessage = ""
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func delete(_ conversation: Conversation) async {
        do {
            try await API.deleteConversation(conversation.session_id)
            conversations.removeAll { $0.session_id == conversation.session_id }
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// MARK: - Detail

struct ConversationDetailView: View {
    let conversation: Conversation

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                ForEach(conversation.messages) { message in
                    if message.role == "user" {
                        HStack {
                            Spacer(minLength: 48)
                            Text(message.content ?? "")
                                .font(.body)
                                .foregroundStyle(.white)
                                .padding(.horizontal, 14).padding(.vertical, 10)
                                .background(EvilifeTheme.brand, in: RoundedRectangle(cornerRadius: 18))
                        }
                    } else {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(message.modulePlan ?? []) { module in
                                ModuleCardView(module: module)
                            }
                            if (message.modulePlan ?? []).isEmpty, let content = message.content, !content.isEmpty {
                                Text(content).font(.body)
                                    .padding(14)
                                    .background(EvilifeTheme.cardBg, in: RoundedRectangle(cornerRadius: 18))
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
            .padding(16)
        }
        .background(EvilifeTheme.pageBg)
        .navigationTitle(conversation.title)
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    HistoryView().environmentObject(AppState())
}
