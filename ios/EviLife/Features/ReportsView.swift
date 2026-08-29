import SwiftUI
import UniformTypeIdentifiers

struct ReportsView: View {
    @State private var showImporter = false
    @State private var analysis: ReportAnalysis?
    @State private var history: [[String: JSONValue]] = []
    @State private var busy = false
    @State private var errorMessage = ""

    var body: some View {
        NavigationStack {
            List {
                uploadSection
                if analysis != nil {
                    analysisSection
                }
                historySection
            }
            .listStyle(.insetGrouped)
            .navigationTitle("报告")
            .task { await loadHistory() }
            .fileImporter(
                isPresented: $showImporter,
                allowedContentTypes: [.pdf, .plainText, .commaSeparatedText, .image],
                allowsMultipleSelection: false
            ) { result in
                Task { await handleImport(result) }
            }
        }
    }

    private var uploadSection: some View {
        Section {
            Button {
                showImporter = true
            } label: {
                HStack {
                    Image(systemName: "doc.badge.plus").foregroundStyle(EvilifeTheme.brand)
                    Text("添加报告")
                    Spacer()
                    if busy { ProgressView().controlSize(.small) }
                }
            }
            .disabled(busy)
            if !errorMessage.isEmpty {
                Text(errorMessage).font(.footnote).foregroundStyle(EvilifeTheme.riskRefused)
            }
        } footer: {
            Text("结果仅供整理，请以原报告为准。")
        }
    }

    private var analysisSection: some View {
        Section {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "doc.text.magnifyingglass")
                        .foregroundStyle(EvilifeTheme.brand)
                    Text(analysis?.file_name ?? "报告")
                        .font(.subheadline.weight(.semibold))
                }
                if let summary = analysis?.summary {
                    Text(summary).font(.footnote).fixedSize(horizontal: false, vertical: true)
                }
                ForEach(analysis?.items ?? []) { item in
                    VStack(alignment: .leading, spacing: 3) {
                        HStack {
                            Text(item.name).font(.footnote.weight(.medium))
                            Spacer()
                            flagBadge(item.flag)
                        }
                        HStack(spacing: 6) {
                            Text("\(item.value) \(item.unit)")
                                .font(.footnote.monospacedDigit())
                            if !item.reference_range.isEmpty {
                                Text("· \(item.reference_range)")
                                    .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                            }
                        }
                    }
                }
                let limitations = analysis?.limitations ?? []
                if !limitations.isEmpty {
                    DisclosureGroup("注意事项 \(limitations.count)") {
                        ForEach(limitations, id: \.self) { limitation in
                            Text(limitation)
                                .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                        }
                    }
                    .font(.caption)
                }
            }
        } header: {
            Text("结果")
        }
    }

    private var historySection: some View {
        Section("历史报告") {
            if history.isEmpty {
                Text("暂无报告").font(.footnote).foregroundStyle(EvilifeTheme.textTertiary)
            }
            ForEach(history.indices, id: \.self) { index in
                let item = history[index]
                VStack(alignment: .leading, spacing: 3) {
                    Text(item["file_name"]?.string ?? item["id"]?.string ?? "报告 \(index + 1)")
                        .font(.footnote.weight(.medium))
                    if let createdAt = item["created_at"]?.string {
                        Text(ISODate.localShort(createdAt)).font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func flagBadge(_ flag: String) -> some View {
        let (label, color): (String, Color) = {
            switch flag {
            case "high": return ("↑ 偏高", EvilifeTheme.riskRefused)
            case "low": return ("↓ 偏低", EvilifeTheme.partly)
            case "normal": return ("正常", EvilifeTheme.supported)
            default: return ("未标", EvilifeTheme.insufficient)
            }
        }()
        Text(label).font(.caption2.weight(.bold))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(color.opacity(0.12), in: Capsule())
            .foregroundStyle(color)
    }

    private func handleImport(_ result: Result<[URL], Error>) async {
        do {
            guard let url = try result.get().first else { return }
            let accessing = url.startAccessingSecurityScopedResource()
            defer { if accessing { url.stopAccessingSecurityScopedResource() } }
            let data = try Data(contentsOf: url)
            guard data.count <= 20 * 1024 * 1024 else {
                errorMessage = "体检报告不能超过 20 MB。"
                return
            }
            busy = true
            errorMessage = ""
            defer { busy = false }
            let mime = Self.mime(for: url.pathExtension)
            analysis = try await API.analyzeReport(
                fileData: data, fileName: url.lastPathComponent, mimeType: mime)
            await loadHistory()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func loadHistory() async {
        history = (try? await API.listReports()) ?? []
    }

    private static func mime(for ext: String) -> String {
        switch ext.lowercased() {
        case "pdf": return "application/pdf"
        case "txt": return "text/plain"
        case "csv": return "text/csv"
        case "png": return "image/png"
        case "webp": return "image/webp"
        default: return "image/jpeg"
        }
    }
}

#Preview {
    ReportsView()
}
