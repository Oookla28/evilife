import SwiftUI

struct TodayView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = TodayViewModel()

    var body: some View {
        NavigationStack {
            List {
                fastingSection
                mealsSection
                observationsSection
            }
            .listStyle(.insetGrouped)
            .navigationTitle("今日")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    DatePicker("日期", selection: $viewModel.selectedDate, displayedComponents: .date)
                        .labelsHidden()
                        .environment(\.locale, Locale(identifier: "zh_CN"))
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        viewModel.showRecordSheet = true
                    } label: {
                        Label("记录", systemImage: "plus.circle.fill")
                    }
                }
            }
            .sheet(isPresented: $viewModel.showRecordSheet) {
                ObservationSheet { input in
                    await viewModel.saveObservation(input)
                }
            }
            .refreshable { await viewModel.load() }
            .task { await viewModel.load() }
            .onChange(of: viewModel.selectedDate) {
                Task { await viewModel.load() }
            }
        }
    }

    // MARK: Fasting

    private var fastingSection: some View {
        Section("禁食") {
            if let active = viewModel.summary?.fasts.first(where: { $0.status == "active" }) {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "timer")
                            .foregroundStyle(.purple)
                        Text("进行中的禁食").font(.subheadline.weight(.semibold))
                        Spacer()
                        Text("目标 \(active.goal_hours.formatted(.number.precision(.fractionLength(0...1)))) 小时")
                            .font(.caption)
                            .foregroundStyle(EvilifeTheme.textSecondary)
                    }
                    if let start = ISODate.parse(active.start_at) {
                        let elapsed = Date().timeIntervalSince(start)
                        let progress = min(elapsed / (active.goal_hours * 3600), 1.5)
                        ProgressView(value: progress)
                            .tint(.purple)
                        Text(elapsedText(elapsed))
                            .font(.footnote.monospacedDigit())
                            .foregroundStyle(EvilifeTheme.textSecondary)
                    }
                    Button("结束禁食", role: .destructive) {
                        Task { await viewModel.endFast(active.id) }
                    }
                    .font(.footnote)
                }
            } else {
                Button {
                    Task { await viewModel.startFast() }
                } label: {
                    HStack {
                        Image(systemName: "timer").foregroundStyle(.purple)
                        Text("开始 16 小时禁食")
                        Spacer()
                        if viewModel.busy { ProgressView().controlSize(.small) }
                    }
                }
                .disabled(viewModel.busy)
            }
            let completed = viewModel.summary?.fasts.filter { $0.status != "active" } ?? []
            ForEach(completed) { fast in
                HStack {
                    Text("\(ISODate.localShort(fast.start_at)) 起")
                    Spacer()
                    Text("\(fast.goal_hours.formatted(.number.precision(.fractionLength(0...1)))) 小时")
                }
                .font(.footnote)
                .foregroundStyle(EvilifeTheme.textSecondary)
            }
        }
    }

    private func elapsedText(_ elapsed: TimeInterval) -> String {
        let hours = Int(elapsed) / 3600
        let minutes = (Int(elapsed) % 3600) / 60
        return String(format: "已进行 %d 小时 %02d 分钟", hours, minutes)
    }

    // MARK: Meals

    private var mealsSection: some View {
        Section("餐食") {
            let meals = viewModel.summary?.meals ?? []
            if meals.isEmpty {
                Text("今天还没有餐食记录。在问答里发送餐食照片即可自动识别并保存。")
                    .font(.footnote)
                    .foregroundStyle(EvilifeTheme.textTertiary)
            }
            ForEach(meals) { meal in
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("\(meal.items?.count ?? 0) 项 · \(ISODate.time(meal.created_at))")
                            .font(.caption.weight(.semibold))
                        Spacer()
                        let calories = meal.estimated_total_calories
                        if calories.count == 2 {
                            Text("\(Int(calories[0]))–\(Int(calories[1])) kcal")
                                .font(.caption.weight(.medium))
                                .foregroundStyle(.orange)
                        }
                    }
                    if let items = meal.items {
                        ForEach(items) { item in
                            HStack {
                                Text(item.name).font(.footnote)
                                Spacer()
                                Text(item.portion).font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                            }
                        }
                    }
                }
            }
        }
    }

    // MARK: Observations

    private var observationsSection: some View {
        Section("健康记录") {
            let observations = viewModel.summary?.observations ?? []
            if observations.isEmpty {
                Text("今天还没有记录。点右上角 + 快速添加饮水、步数、体重等。")
                    .font(.footnote)
                    .foregroundStyle(EvilifeTheme.textTertiary)
            }
            ForEach(observations) { record in
                HStack {
                    Image(systemName: kindIcon(record.kind))
                        .foregroundStyle(kindColor(record.kind))
                        .frame(width: 24)
                    Text(observationKindLabel(record.kind)).font(.subheadline)
                    Spacer()
                    if record.kind == "note" {
                        Text(record.note ?? "").font(.caption).foregroundStyle(EvilifeTheme.textSecondary)
                    } else if let value = record.value {
                        Text("\(value.formatted(.number.precision(.fractionLength(0...2)))) \(observationUnit(record.kind))")
                            .font(.subheadline.monospacedDigit().weight(.medium))
                    }
                    if record.source == "device" {
                        Image(systemName: "apple.logo")
                            .font(.caption2)
                            .foregroundStyle(EvilifeTheme.textTertiary)
                    }
                }
                .swipeActions {
                    Button("删除", role: .destructive) {
                        Task { await viewModel.deleteObservation(record.id) }
                    }
                }
            }
        }
    }

    private func kindIcon(_ kind: String) -> String {
        switch kind {
        case "water_ml": return "drop.fill"
        case "steps": return "figure.walk"
        case "sleep_minutes": return "moon.zzz.fill"
        case "weight_kg": return "scalemass.fill"
        case "waist_cm": return "ruler"
        case "resting_heart_rate": return "heart.fill"
        case "mood_score": return "face.smiling"
        default: return "note.text"
        }
    }

    private func kindColor(_ kind: String) -> Color {
        switch kind {
        case "water_ml": return .blue
        case "steps": return .green
        case "sleep_minutes": return .indigo
        case "weight_kg", "waist_cm": return .orange
        case "resting_heart_rate": return .red
        case "mood_score": return .yellow
        default: return EvilifeTheme.textTertiary
        }
    }
}

// MARK: - ViewModel

@MainActor
final class TodayViewModel: ObservableObject {
    @Published var selectedDate = Date()
    @Published var summary: TodaySummary?
    @Published var busy = false
    @Published var showRecordSheet = false
    @Published var errorMessage: String?

    private var dateString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "Asia/Shanghai")
        return formatter.string(from: selectedDate)
    }

    func load() async {
        busy = true
        defer { busy = false }
        do {
            summary = try await API.today(date: dateString)
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func startFast(goalHours: Double = 16) async {
        do {
            _ = try await API.startFast(goalHours: goalHours)
            await load()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func endFast(_ id: String) async {
        do {
            _ = try await API.endFast(id)
            await load()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func saveObservation(_ input: ObservationCreate) async {
        do {
            _ = try await API.addObservation(input)
            await load()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func deleteObservation(_ id: String) async {
        do {
            _ = try await API.deleteObservation(id)
            await load()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// MARK: - Quick record sheet

struct ObservationSheet: View {
    let onSave: (ObservationCreate) async -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var kind = "water_ml"
    @State private var valueText = ""
    @State private var note = ""
    @State private var saving = false
    @State private var errorMessage = ""

    private let kinds: [(String, String)] = [
        ("water_ml", "饮水 (ml)"),
        ("steps", "步数 (步)"),
        ("sleep_minutes", "睡眠 (分钟)"),
        ("weight_kg", "体重 (kg)"),
        ("waist_cm", "腰围 (cm)"),
        ("resting_heart_rate", "静息心率 (次/分)"),
        ("mood_score", "心情 (1–5)"),
        ("note", "备注"),
    ]

    var body: some View {
        NavigationStack {
            Form {
                Section("类型") {
                    Picker("类型", selection: $kind) {
                        ForEach(kinds, id: \.0) { item in
                            Text(item.1).tag(item.0)
                        }
                    }
                    .pickerStyle(.menu)
                }
                Section("数值") {
                    if kind == "note" {
                        TextField("写点什么…", text: $note, axis: .vertical)
                            .lineLimit(2...6)
                    } else {
                        TextField(placeholder, text: $valueText)
                            .keyboardType(kind == "mood_score" ? .numberPad : .decimalPad)
                    }
                }
                if !errorMessage.isEmpty {
                    Section {
                        Text(errorMessage).font(.footnote).foregroundStyle(EvilifeTheme.riskRefused)
                    }
                }
                Section {
                    Button {
                        Task { await save() }
                    } label: {
                        if saving {
                            ProgressView().frame(maxWidth: .infinity)
                        } else {
                            Text("保存记录").frame(maxWidth: .infinity)
                        }
                    }
                    .disabled(saving || (!isValid && kind != "note") || (kind == "note" && note.isEmpty))
                }
                Section {
                    Text("这些是本人主动记录，不是 AI 测量值。")
                        .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                }
            }
            .navigationTitle("快速记录")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
            }
        }
    }

    private var placeholder: String {
        switch kind {
        case "water_ml": return "例如 500"
        case "steps": return "例如 8000"
        case "sleep_minutes": return "例如 420"
        case "weight_kg": return "例如 65.5"
        case "waist_cm": return "例如 80"
        case "resting_heart_rate": return "例如 62"
        case "mood_score": return "1–5"
        default: return ""
        }
    }

    private var isValid: Bool {
        guard let value = Double(valueText), value >= 0 else { return false }
        if kind == "mood_score" { return (1...5).contains(value) }
        return true
    }

    private func save() async {
        saving = true
        errorMessage = ""
        defer { saving = false }
        let input: ObservationCreate
        if kind == "note" {
            input = ObservationCreate(kind: kind, note: note, source: "self_report")
        } else if let value = Double(valueText) {
            input = ObservationCreate(kind: kind, value: value, source: "self_report")
        } else {
            errorMessage = "请输入有效数值。"
            return
        }
        await onSave(input)
        dismiss()
    }
}

#Preview {
    TodayView().environmentObject(AppState())
}
