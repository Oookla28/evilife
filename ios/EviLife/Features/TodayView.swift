import SwiftUI
import PhotosUI
import UIKit

struct TodayView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = TodayViewModel()
    @State private var showCalendar = false

    @State private var showMealPickerChoice = false
    @State private var showMealCamera = false
    @State private var showMealLibrary = false
    @State private var showMealGallery = false
    @State private var mealPickerItem: PhotosPickerItem?
    @State private var mealModule: ModulePlanItem?
    @State private var mealUploading = false
    @State private var mealError = ""

    var body: some View {
        NavigationStack {
            List {
                if !viewModel.isToday {
                    Button {
                        viewModel.goToToday()
                    } label: {
                        Label("回到今天", systemImage: "arrow.uturn.backward")
                            .font(.footnote.weight(.medium))
                            .frame(maxWidth: .infinity)
                    }
                }
                daySummarySection
                if let error = viewModel.errorMessage {
                    Text(error)
                        .font(.footnote)
                        .foregroundStyle(EvilifeTheme.riskRefused)
                }
                mealsSection
                observationsSection
            }
            .listStyle(.insetGrouped)
            .navigationTitle(dateTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    HStack(spacing: 14) {
                        Button {
                            viewModel.shiftDays(-1)
                        } label: {
                            Image(systemName: "chevron.left")
                        }
                        .accessibilityLabel("前一天")
                        Button {
                            viewModel.shiftDays(1)
                        } label: {
                            Image(systemName: "chevron.right")
                        }
                        .disabled(viewModel.isToday)
                        .accessibilityLabel("后一天")
                    }
                    .font(.footnote.weight(.semibold))
                }
                ToolbarItem(placement: .principal) {
                    HStack(spacing: 6) {
                        Button {
                            viewModel.goToToday()
                        } label: {
                            Text(dateTitle).font(.headline)
                        }
                        .buttonStyle(.plain)
                        .disabled(viewModel.isToday)
                        Button {
                            showCalendar = true
                        } label: {
                            Image(systemName: "calendar")
                                .font(.caption)
                                .foregroundStyle(EvilifeTheme.textTertiary)
                        }
                        .accessibilityLabel("选择日期")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        viewModel.showRecordSheet = true
                    } label: {
                        Image(systemName: "plus")
                    }
                    .accessibilityLabel("添加记录")
                }
            }
            .sheet(isPresented: $viewModel.showRecordSheet) {
                ObservationSheet { input in
                    await viewModel.saveObservation(input)
                }
            }
            .sheet(isPresented: $showCalendar) {
                NavigationStack {
                    DatePicker("选择日期", selection: $viewModel.selectedDate, displayedComponents: .date)
                        .datePickerStyle(.graphical)
                        .environment(\.locale, Locale(identifier: "zh_CN"))
                        .padding()
                        .navigationTitle("选择日期")
                        .navigationBarTitleDisplayMode(.inline)
                        .toolbar {
                            ToolbarItem(placement: .confirmationAction) {
                                Button("完成") { showCalendar = false }
                            }
                        }
                }
                .presentationDetents([.medium])
            }
            .sheet(isPresented: $showMealCamera) {
                CameraPicker { image in
                    if let data = image.jpegData(compressionQuality: 0.85) {
                        Task { await analyzeMeal(data, mime: "image/jpeg") }
                    }
                }
                .ignoresSafeArea()
            }
            .photosPicker(isPresented: $showMealLibrary, selection: $mealPickerItem, matching: .images)
            .sheet(isPresented: $showMealGallery) {
                MealPhotoGalleryView()
            }
            .onChange(of: mealPickerItem) { _, newItem in
                Task {
                    guard let newItem,
                          let data = try? await newItem.loadTransferable(type: Data.self) else { return }
                    let ext = newItem.supportedContentTypes.first?.preferredFilenameExtension ?? "jpg"
                    let mime = ext == "png" ? "image/png" : (ext == "webp" ? "image/webp" : "image/jpeg")
                    await analyzeMeal(data, mime: mime)
                }
            }
            .sheet(item: $mealModule) { module in
                NavigationStack {
                    ScrollView {
                        MealAnalyzerCard(module: module)
                            .padding()
                    }
                    .background(EvilifeTheme.pageBg)
                    .navigationTitle("餐食识别")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .confirmationAction) {
                            Button("完成") {
                                mealModule = nil
                                Task { await viewModel.load() }
                            }
                        }
                    }
                }
                .presentationDetents([.medium, .large])
            }
            .refreshable { await viewModel.load() }
            .task { await viewModel.load() }
            .onChange(of: viewModel.selectedDate) {
                Task { await viewModel.load() }
            }
        }
    }

    private var dateTitle: String {
        if Calendar.current.isDateInToday(viewModel.selectedDate) { return "今日" }
        if Calendar.current.isDateInYesterday(viewModel.selectedDate) { return "昨天" }
        let formatter = DateFormatter()
        formatter.dateFormat = "M月d日 EEE"
        formatter.locale = Locale(identifier: "zh_CN")
        return formatter.string(from: viewModel.selectedDate)
    }

    // MARK: 当日摘要（浏览过去记录时快速概览）

    private var daySummarySection: some View {
        let observations = viewModel.summary?.observations ?? []
        let lastOf: (String) -> ObservationRecord? = { kind in
            observations.last { $0.kind == kind }
        }
        let sumOf: (String) -> Double = { kind in
            observations.filter { $0.kind == kind }.compactMap(\.value).reduce(0, +)
        }
        let steps = sumOf("steps")
        let sleep = lastOf("sleep_minutes")?.value
        let weight = lastOf("weight_kg")?.value
        let water = sumOf("water_ml")
        let heart = lastOf("resting_heart_rate")?.value
        let hasData = steps > 0 || sleep != nil || weight != nil || water > 0 || heart != nil
        return Section {
            if hasData {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        summaryChip("figure.walk", "步数", steps.formatted(.number.precision(.fractionLength(0))), .green)
                        if let sleep {
                            summaryChip("moon.zzz.fill", "睡眠", sleepDurationLabel(sleep), .indigo)
                        }
                        if let heart {
                            summaryChip("heart.fill", "静息心率", "\(heart.formatted(.number.precision(.fractionLength(0...1)))) 次/分", .red)
                        }
                        if let weight {
                            summaryChip("scalemass.fill", "体重", "\(weight.formatted(.number.precision(.fractionLength(1)))) kg", .orange)
                        }
                        if water > 0 {
                            summaryChip("drop.fill", "饮水", "\(Int(water)) ml", .blue)
                        }
                    }
                }
            } else {
                Text(viewModel.isToday ? "今天还没有记录，点右上角 + 添加。" : "这一天没有记录。")
                    .font(.footnote)
                    .foregroundStyle(EvilifeTheme.textTertiary)
            }
        } header: {
            Text("这一天")
        }
    }

    private func summaryChip(_ icon: String, _ label: String, _ value: String, _ color: Color) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(color)
            VStack(alignment: .leading, spacing: 0) {
                Text(value)
                    .font(.footnote.monospacedDigit().weight(.semibold))
                Text(label)
                    .font(.caption2)
                    .foregroundStyle(EvilifeTheme.textTertiary)
            }
        }
        .padding(.horizontal, 10).padding(.vertical, 6)
        .background(EvilifeTheme.pageBg, in: RoundedRectangle(cornerRadius: 10))
    }

    // MARK: Fasting

    private var mealsSection: some View {
        Section {
            let meals = viewModel.summary?.meals ?? []
            if meals.isEmpty {
                Text("拍一张餐食照片，自动识别食物和热量")
                    .font(.footnote)
                    .foregroundStyle(EvilifeTheme.textTertiary)
            }
            ForEach(meals) { meal in
                DisclosureGroup {
                    if let items = meal.items {
                        ForEach(items) { item in
                            HStack {
                                Text(item.name).font(.footnote)
                                Spacer()
                                Text(item.portion).font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                            }
                        }
                    }
                } label: {
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
                }
            }
            if !mealError.isEmpty {
                Text(mealError)
                    .font(.footnote)
                    .foregroundStyle(EvilifeTheme.riskRefused)
            }
            Button {
                showMealPickerChoice = true
            } label: {
                HStack(spacing: 6) {
                    if mealUploading {
                        ProgressView().controlSize(.small)
                        Text("正在识别…").font(.footnote)
                    } else {
                        Image(systemName: "camera.fill")
                        Text("拍照记餐").font(.footnote.weight(.medium))
                    }
                }
            }
            .disabled(mealUploading)
            Button {
                showMealGallery = true
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "photo.on.rectangle.angled")
                    Text("照片墙").font(.footnote.weight(.medium))
                }
            }
        } header: {
            Text("餐食")
        }
        .confirmationDialog("记一餐", isPresented: $showMealPickerChoice, titleVisibility: .visible) {
            Button("拍照") { showMealCamera = true }
            Button("从相册选择") { showMealLibrary = true }
            Button("取消", role: .cancel) { }
        }
    }

    private func analyzeMeal(_ data: Data, mime: String) async {
        MealPhotoStore.save(data) // 自动存入本地照片墙
        mealUploading = true
        mealError = ""
        defer { mealUploading = false }
        do {
            let response = try await API.orchestrate(
                sessionId: "s-ios-meals-\(UUID().uuidString.prefix(8))",
                mode: "auto",
                text: nil,
                image: data,
                imageName: "meal.jpg",
                imageMime: mime)
            if let module = response.module_plan.first(where: { $0.type == "MealAnalyzer" }) {
                let analysisError = module.props["analysis_error"]?.string
                let items = module.props["items"]?.array ?? []
                print("[MEAL] backend module: error=\(analysisError ?? "nil") items=\(items.count)")
                if analysisError == nil || analysisError?.isEmpty == true,
                   !items.isEmpty {
                    mealModule = module
                    return
                }
                // 后端视觉未配置 → 回退直连多模态 API（fallback 内部会设置 mealError）
                if await fallbackToDirectMeal(data, mime: mime) { return }
                if mealError.isEmpty {
                    mealError = "餐食识别失败，请换一张清晰的餐食照片。"
                }
            } else {
                mealError = "没有生成餐食识别结果，请换一张清晰的餐食照片。"
            }
        } catch {
            mealError = error.localizedDescription
        }
    }

    /// 后端视觉识别不可用时，回退到直连 API 的多模态模型识别。
    private func fallbackToDirectMeal(_ data: Data, mime: String) async -> Bool {
        let store = APIConfigStore.shared
        print("[MEAL] fallback start: hasKey=\(store.hasKey) mode=\(store.visionMode) model=\(store.multimodalModel) base=\(store.baseURL)")
        guard store.hasKey else {
            mealError = "后端未配置视觉识别，App 里也还没填 DeepSeek Key。请到 问答页 → ⋯ → API 接入：填 Key 保存后重拍。"
            print("[MEAL] no app key")
            return false
        }
        do {
            let result: DirectAPI.MealVisionResult
            if store.visionMode == "bridge" {
                result = try await DirectAPI.chatVisionMeal(
                    imageData: data, imageMime: mime,
                    base: store.visionBaseURL, key: store.visionKey,
                    model: store.visionModel, maxTokens: store.maxTokens)
            } else {
                result = try await DirectAPI.chatVisionMeal(
                    imageData: data, imageMime: mime,
                    base: store.baseURL, key: store.apiKey,
                    model: store.multimodalModel, maxTokens: store.maxTokens)
            }
            print("[MEAL] direct result items=\(result.items.count)")
            guard !result.items.isEmpty else {
                let reason = result.overallUncertainty?.isEmpty == false
                    ? result.overallUncertainty!
                    : "图片里没有识别到食物"
                mealError = "没有识别到食物：\(reason)"
                return false
            }
            mealModule = Self.syntheticMealModule(result)
            return true
        } catch {
            print("[MEAL] direct error: \(error)")
            mealError = "直连识别失败：\(error.localizedDescription)"
            return false
        }
    }

    /// 把直连多模态的识别结果包装成 MealAnalyzer 模块（复用确认保存卡片）。
    private static func syntheticMealModule(_ result: DirectAPI.MealVisionResult) -> ModulePlanItem {
        let actionId = "action-meal-ios-\(UUID().uuidString.prefix(8))"
        let items: [JSONValue] = result.items.enumerated().map { index, item in
            var object: [String: JSONValue] = [
                "id": .string("food-\(index + 1)"),
                "name": .string(item.name),
                "portion": .string(item.portion),
                "estimated_calories": .array(item.calories.map { .number(Double($0)) }),
            ]
            if let grams = item.portionGrams {
                object["portion_grams"] = .array(grams.map { .number(Double($0)) })
            }
            if let center = item.caloriesCenter {
                object["estimated_calories_center"] = .number(Double(center))
            }
            if let confidence = item.confidence {
                object["confidence"] = .string(confidence)
            }
            if let basis = item.referenceBasis {
                object["reference_basis"] = .string(basis)
            }
            if let uncertainty = item.uncertainty {
                object["uncertainty"] = .string(uncertainty)
            }
            return .object(object)
        }
        var props: [String: JSONValue] = [
            "action_id": .string(actionId),
            "items": .array(items),
            "total_calories": .array(result.totalCalories.map { .number(Double($0)) }),
            "status": .string("ready"),
        ]
        if let center = result.totalCaloriesCenter {
            props["total_calories_center"] = .number(Double(center))
        }
        if let uncertainty = result.overallUncertainty {
            props["overall_uncertainty"] = .string(uncertainty)
        }
        return ModulePlanItem(
            module_id: "meal-ios-\(UUID().uuidString.prefix(8))",
            type: "MealAnalyzer",
            version: "1",
            priority: 1,
            status: "ready",
            props: props)
    }

    // MARK: Observations

    private var observationsSection: some View {
        Section("记录") {
            let observations = viewModel.summary?.observations ?? []
            if observations.isEmpty {
                Text("暂无记录")
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
                        Text(record.note ?? "")
                            .font(.caption)
                            .foregroundStyle(EvilifeTheme.textSecondary)
                            .lineLimit(1)
                    } else if let value = record.value {
                        Text(record.kind == "sleep_minutes" ? sleepDurationLabel(value) : "\(value.formatted(.number.precision(.fractionLength(0...2)))) \(observationUnit(record.kind))")
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

    /// 是否正在查看今天（用于禁用「后一天」按钮等）
    var isToday: Bool { dateString == ISODate.today() }

    func shiftDays(_ delta: Int) {
        guard let newDate = Calendar.current.date(byAdding: .day, value: delta, to: selectedDate) else { return }
        selectedDate = newDate
    }

    func goToToday() {
        selectedDate = Date()
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
        ("water_ml", "饮水"),
        ("steps", "步数"),
        ("sleep_minutes", "睡眠"),
        ("weight_kg", "体重"),
        ("waist_cm", "腰围"),
        ("resting_heart_rate", "静息心率"),
        ("mood_score", "心情"),
        ("note", "备注"),
    ]

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("项目", selection: $kind) {
                        ForEach(kinds, id: \.0) { item in
                            Text(item.1).tag(item.0)
                        }
                    }
                    .pickerStyle(.menu)
                    if kind == "note" {
                        TextField("备注", text: $note, axis: .vertical)
                            .lineLimit(2...6)
                    } else {
                        HStack {
                            TextField(placeholder, text: $valueText)
                                .keyboardType(kind == "mood_score" ? .numberPad : .decimalPad)
                            Text(observationUnit(kind))
                                .font(.footnote)
                                .foregroundStyle(EvilifeTheme.textTertiary)
                        }
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
                            Text("保存").frame(maxWidth: .infinity)
                        }
                    }
                    .disabled(saving || (!isValid && kind != "note") || (kind == "note" && note.isEmpty))
                }
            }
            .navigationTitle("记录")
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
            input = ObservationCreate(kind: kind, note: note, source: "self_report", observedAt: ISODate.localNoon())
        } else if let value = Double(valueText) {
            input = ObservationCreate(kind: kind, value: value, source: "self_report", observedAt: ISODate.localNoon())
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
