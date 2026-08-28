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
                if let analysis {
                    analysisSection
                }
                historySection
                disclaimerSection
            }
            .listStyle(.insetGrouped)
            .navigationTitle("体检报告")
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
                    Text("上传体检报告（PDF / TXT / CSV / 图片）")
                    Spacer()
                    if busy { ProgressView().controlSize(.small) }
                }
            }
            .disabled(busy)
            if !errorMessage.isEmpty {
                Text(errorMessage).font(.footnote).foregroundStyle(EvilifeTheme.riskRefused)
            }
        } header: {
            Text("报告分析")
        } footer: {
            Text("结构化结果只用于整理报告原文，不构成诊断或治疗建议；请逐项与原报告核对。")
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
                    Spacer()
                    if let source = analysis?.source {
                        Text(sourceLabel(source))
                            .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                    }
                }
                if let summary = analysis?.summary {
                    Text(summary).font(.footnote).fixedSize(horizontal: false, vertical: true)
                }
                ForEach(analysis?.items ?? []) { item in
                    HStack {
                        Text(item.name).font(.footnote)
                        Spacer()
                        Text("\(item.value) \(item.unit)")
                            .font(.footnote.monospacedDigit().weight(.medium))
                        if !item.reference_range.isEmpty {
                            Text("参考 \(item.reference_range)")
                                .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                        }
                        flagBadge(item.flag)
                    }
                }
                let limitations = analysis?.limitations ?? []
                if !limitations.isEmpty {
                    ForEach(limitations, id: \.self) { limitation in
                        Text("• \(limitation)")
                            .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                    }
                }
            }
        } header: {
            Text("本次分析结果")
        }
    }

    private var historySection: some View {
        Section("历史报告") {
            if history.isEmpty {
                Text("暂无历史报告。").font(.footnote).foregroundStyle(EvilifeTheme.textTertiary)
            }
            ForEach(history.indices, id: \.self) { index in
                let item = history[index]
                VStack(alignment: .leading, spacing: 3) {
                    Text(item["file_name"]?.string ?? item["id"]?.string ?? "报告 \(index + 1)")
                        .font(.footnote.weight(.medium))
                    if let summary = item["summary"]?.string {
                        Text(summary).font(.caption2).foregroundStyle(EvilifeTheme.textSecondary).lineLimit(2)
                    }
                    if let createdAt = item["created_at"]?.string {
                        Text(ISODate.localShort(createdAt)).font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                    }
                }
            }
        }
    }

    private var disclaimerSection: some View {
        Section {
            Text(AppConfig.medicalDisclaimer)
                .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
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

    private func sourceLabel(_ source: String) -> String {
        switch source {
        case "text_extraction": return "文本结构化"
        case "deepseek_vl2": return "视觉模型识别"
        default: return "受限降级"
        }
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
