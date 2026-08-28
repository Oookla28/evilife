import SwiftUI

// MARK: - Dispatcher

struct ModuleCardView: View {
    let module: ModulePlanItem
    var onSelectOption: (String) -> Void = { _ in }

    var body: some View {
        switch module.type {
        case "EvidenceAnswer", "EvidenceFlow":
            EvidenceAnswerCard(module: module)
        case "SafetyCard":
            SafetyCardView(module: module)
        case "GeneralAnswerCard":
            GeneralAnswerCardView(module: module)
        case "CrisisSupportCard", "ExtremeCrisisCareCard":
            CrisisCardView(module: module)
        case "ClarificationCard":
            ClarificationCardView(module: module, onSelect: onSelectOption)
        case "HealthRecordDraft":
            HealthRecordDraftCard(module: module)
        case "MealAnalyzer":
            MealAnalyzerCard(module: module)
        case "FastingTimer":
            FastingTimerCard(module: module)
        case "DocumentSummary":
            DocumentSummaryCard(module: module)
        case "ChatFeaturePanel":
            ChatFeaturePanelCard(module: module)
        default:
            UnknownModuleCard(module: module)
        }
    }
}

// MARK: - Shared card chrome

struct CardShell<Content: View>: View {
    var tint: Color
    var icon: String
    let content: Content

    init(
        tint: Color = EvilifeTheme.brand,
        icon: String = "cross.case.fill",
        @ViewBuilder content: () -> Content
    ) {
        self.tint = tint
        self.icon = icon
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(tint)
                Text(iconTitle)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(tint)
                    .textCase(.uppercase)
                Spacer()
            }
            content
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(EvilifeTheme.cardBg, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(tint.opacity(0.22), lineWidth: 1))
    }

    private var iconTitle: String {
        switch icon {
        case "shield.fill", "shield.lefthalf.filled": return "安全边界"
        case "text.bubble.fill": return "通用问答"
        case "heart.hand.clipboard.fill", "heart.text.square.fill": return "先照顾此刻的安全"
        case "questionmark.bubble.fill": return "补充信息"
        case "clipboard.badge.plus.fill", "list.clipboard.fill": return "健康记录"
        case "fork.knife": return "餐食识别"
        case "timer": return "禁食计时"
        case "doc.plaintext.fill": return "文档摘要"
        default: return "证据答案"
        }
    }
}

// MARK: - EvidenceAnswer

struct EvidenceAnswerCard: View {
    let module: ModulePlanItem

    private var props: [String: JSONValue] { module.props }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header: gate + strength
            HStack(spacing: 8) {
                if let gate = props["gate_status"]?.string, gate != "normal" {
                    Text(gate == "refused" ? "已拦截" : "降级回答")
                        .font(.caption2.weight(.bold))
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(EvilifeTheme.riskRefused.opacity(0.12), in: Capsule())
                        .foregroundStyle(EvilifeTheme.riskRefused)
                }
                if let strength = props["evidence_strength"]?.string {
                    Text(strengthLabel(strength))
                        .font(.caption2.weight(.bold))
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(EvilifeTheme.brandLight, in: Capsule())
                        .foregroundStyle(EvilifeTheme.brandDark)
                }
                if let topic = props["topic"]?.string {
                    Text(topic).font(.caption2).foregroundStyle(EvilifeTheme.textTertiary).lineLimit(1)
                }
                Spacer()
            }

            // Conclusion
            if let conclusion = props["conclusion"]?.string {
                Text(conclusion)
                    .font(.body.weight(.semibold))
                    .fixedSize(horizontal: false, vertical: true)
            }

            // Verdict
            if let verdict = props["verdict"]?.object {
                VerdictView(verdict: verdict)
            }

            // Explanation
            if let explanation = props["explanation"]?.string, !explanation.isEmpty {
                section("解释") {
                    Text(explanation).font(.subheadline).fixedSize(horizontal: false, vertical: true)
                }
            }

            // Populations
            let target = props["target_population"]?.stringArray ?? []
            let nonTarget = props["non_target_population"]?.stringArray ?? []
            if !target.isEmpty || !nonTarget.isEmpty {
                section("适用人群") {
                    if !target.isEmpty {
                        ForEach(target, id: \.self) { item in
                            bullet("checkmark.circle.fill", color: EvilifeTheme.supported, item)
                        }
                    }
                    if !nonTarget.isEmpty {
                        ForEach(nonTarget, id: \.self) { item in
                            bullet("xmark.circle.fill", color: EvilifeTheme.partly, item)
                        }
                    }
                }
            }

            // Advice
            let advice = props["general_advice"]?.stringArray ?? []
            if !advice.isEmpty {
                section("行动建议") {
                    ForEach(advice, id: \.self) { item in
                        bullet("arrow.right.circle.fill", color: EvilifeTheme.brand, item)
                    }
                }
            }

            // Limitations
            let limitations = props["limitations"]?.stringArray ?? []
            if !limitations.isEmpty {
                section("证据边界") {
                    ForEach(limitations, id: \.self) { item in
                        bullet("exclamationmark.triangle.fill", color: EvilifeTheme.boundary, item)
                    }
                }
            }

            // TCM perspective
            if let tcm = props["tcm_perspective"]?.object {
                section("中医视角") {
                    ForEach(Array(tcm.keys.sorted()), id: \.self) { key in
                        if let value = tcm[key], !value.isNull, !value.displayText.isEmpty {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(key.replacingOccurrences(of: "_", with: " "))
                                    .font(.caption2.weight(.semibold))
                                    .foregroundStyle(EvilifeTheme.textTertiary)
                                Text(value.displayText).font(.footnote)
                            }
                        }
                    }
                }
            }

            // Citations
            if let citations = props["citations"]?.array, !citations.isEmpty {
                CitationsView(citations: citations)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(EvilifeTheme.cardBg, in: RoundedRectangle(cornerRadius: 20))
        .overlay(RoundedRectangle(cornerRadius: 20).stroke(EvilifeTheme.brand.opacity(0.25), lineWidth: 1))
    }

    @ViewBuilder
    private func section(_ title: String, @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(EvilifeTheme.textSecondary)
            content()
        }
    }

    private func bullet(_ icon: String, color: Color, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 6) {
            Image(systemName: icon)
                .font(.footnote)
                .foregroundStyle(color)
                .padding(.top, 1)
            Text(text)
                .font(.footnote)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

// MARK: - Verdict

struct VerdictView: View {
    let verdict: [String: JSONValue]
    @State private var expanded = false

    private var value: String { verdict["verdict"]?.string ?? "insufficient" }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                Text(verdictLabel(value))
                    .font(.headline)
                    .foregroundStyle(verdictColor(value))
                if let confidence = verdict["confidence"]?.double {
                    Text("置信度 \(Int((confidence * 100).rounded()))%")
                        .font(.caption)
                        .foregroundStyle(EvilifeTheme.textSecondary)
                }
                Spacer()
                if let grade = verdict["evidence_grade"]?.string {
                    Text("证据等级 \(grade)")
                        .font(.caption2.weight(.medium))
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(verdictColor(value).opacity(0.12), in: Capsule())
                        .foregroundStyle(verdictColor(value))
                }
            }
            if let reason = verdict["short_reason"]?.string {
                Text(reason).font(.footnote).foregroundStyle(EvilifeTheme.textSecondary)
            }
            if let claim = verdict["claim"]?.string, !claim.isEmpty {
                Text("核验主张：\(claim)")
                    .font(.caption)
                    .foregroundStyle(EvilifeTheme.textTertiary)
            }

            Button {
                withAnimation(.spring(duration: 0.3)) { expanded.toggle() }
            } label: {
                HStack {
                    Text(expanded ? "收起证据明细" : "查看证据明细")
                        .font(.caption.weight(.semibold))
                    Image(systemName: "chevron.down")
                        .font(.caption2)
                        .rotationEffect(.degrees(expanded ? 180 : 0))
                }
                .foregroundStyle(EvilifeTheme.brandDark)
            }
            .buttonStyle(.plain)

            if expanded {
                let supporting = verdict["supporting_evidence"]?.array ?? []
                let opposing = verdict["opposing_evidence"]?.array ?? []
                if !supporting.isEmpty {
                    verdictEvidenceList("支持证据", color: EvilifeTheme.supported, items: supporting)
                }
                if !opposing.isEmpty {
                    verdictEvidenceList("反对证据", color: EvilifeTheme.against, items: opposing)
                }
                let applies = verdict["applies_to"]?.stringArray ?? []
                let notApplies = verdict["does_not_apply_to"]?.stringArray ?? []
                if !applies.isEmpty || !notApplies.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("适用 / 不适用").font(.caption.weight(.semibold)).foregroundStyle(EvilifeTheme.textSecondary)
                        if !applies.isEmpty { Text("适用：\(applies.joined(separator: "；"))").font(.caption) }
                        if !notApplies.isEmpty { Text("不适用：\(notApplies.joined(separator: "；"))").font(.caption) }
                    }
                }
                let uncertainty = verdict["uncertainty"]?.stringArray ?? []
                if !uncertainty.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("不确定性").font(.caption.weight(.semibold)).foregroundStyle(EvilifeTheme.textSecondary)
                        ForEach(uncertainty, id: \.self) { item in
                            Text("• \(item)").font(.caption)
                        }
                    }
                }
                let couldChange = verdict["what_could_change_this_verdict"]?.stringArray ?? []
                if !couldChange.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("什么可能改变该裁决").font(.caption.weight(.semibold)).foregroundStyle(EvilifeTheme.textSecondary)
                        ForEach(couldChange, id: \.self) { item in
                            Text("• \(item)").font(.caption)
                        }
                    }
                }
            }
        }
        .padding(12)
        .background(verdictColor(value).opacity(0.08), in: RoundedRectangle(cornerRadius: 14))
    }

    @ViewBuilder
    private func verdictEvidenceList(_ title: String, color: Color, items: [JSONValue]) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.caption.weight(.semibold)).foregroundStyle(color)
            ForEach(items.indices, id: \.self) { index in
                let item = items[index].object ?? [:]
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(item["title"]?.string ?? "未命名来源")" + (item["year"]?.int.map { "（\($0)）" } ?? ""))
                        .font(.caption.weight(.medium))
                    if let finding = item["finding"]?.string {
                        Text(finding).font(.caption2).foregroundStyle(EvilifeTheme.textSecondary)
                    }
                }
            }
        }
    }
}

// MARK: - Citations

struct CitationsView: View {
    let citations: [JSONValue]
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Button {
                withAnimation(.spring(duration: 0.3)) { expanded.toggle() }
            } label: {
                HStack {
                    Image(systemName: "link")
                        .font(.caption)
                    Text("引用来源（\(citations.count)）")
                        .font(.caption.weight(.semibold))
                    Spacer()
                    Image(systemName: "chevron.down")
                        .font(.caption2)
                        .rotationEffect(.degrees(expanded ? 180 : 0))
                }
                .foregroundStyle(EvilifeTheme.brandDark)
            }
            .buttonStyle(.plain)

            if expanded {
                ForEach(citations.indices, id: \.self) { index in
                    let citation = citations[index].object ?? [:]
                    VStack(alignment: .leading, spacing: 3) {
                        Text("\(citation["evidence_id"]?.string ?? "E\(index + 1)") · \(citation["title"]?.string ?? "未命名来源")")
                            .font(.caption.weight(.medium))
                        HStack(spacing: 6) {
                            if let type = citation["source_type"]?.string {
                                Text(type).font(.caption2)
                            }
                            if let year = citation["year"]?.int {
                                Text(String(year)).font(.caption2)
                            }
                            if let org = citation["organization"]?.string {
                                Text(org).font(.caption2).lineLimit(1)
                            }
                            if let channel = citation["channel"]?.string {
                                Text(channel == "curated_database" ? "策展语料库" : "实时医学检索")
                                    .font(.caption2.weight(.semibold))
                                    .padding(.horizontal, 6).padding(.vertical, 1)
                                    .background(EvilifeTheme.brandLight, in: Capsule())
                            }
                            Spacer()
                            if let url = citation["url"]?.string, let link = URL(string: url) {
                                Link(destination: link) {
                                    Image(systemName: "arrow.up.right.square")
                                        .font(.caption)
                                }
                            }
                        }
                        .foregroundStyle(EvilifeTheme.textSecondary)
                    }
                    .padding(8)
                    .background(EvilifeTheme.pageBg, in: RoundedRectangle(cornerRadius: 10))
                }
            }
        }
    }
}

// MARK: - System cards

struct SafetyCardView: View {
    let module: ModulePlanItem

    var body: some View {
        CardShell(tint: EvilifeTheme.riskRefused, icon: "shield.fill") {
            Text(module.props["title"]?.string ?? "安全提示")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(EvilifeTheme.riskRefused)
            if let message = module.props["message"]?.string {
                Text(message).font(.footnote).fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

struct GeneralAnswerCardView: View {
    let module: ModulePlanItem

    var body: some View {
        CardShell(tint: .blue, icon: "text.bubble.fill") {
            if let title = module.props["title"]?.string {
                Text(title).font(.subheadline.weight(.semibold))
            }
            if let answer = module.props["answer"]?.string {
                Text(answer).font(.footnote).fixedSize(horizontal: false, vertical: true)
            }
            if let reason = module.props["classification_reason"]?.string {
                Text("分类依据：\(reason)")
                    .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
            }
            let points = module.props["key_points"]?.stringArray ?? []
            if !points.isEmpty {
                ForEach(points, id: \.self) { point in
                    HStack(alignment: .top, spacing: 6) {
                        Image(systemName: "circle.fill").font(.system(size: 5)).padding(.top, 5)
                        Text(point).font(.caption)
                    }
                }
            }
            let limitations = module.props["limitations"]?.stringArray ?? []
            if !limitations.isEmpty {
                Text("边界：\(limitations.joined(separator: "；"))")
                    .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
            }
            if let boundary = module.props["boundary_label"]?.string {
                Text(boundary)
                    .font(.caption2.weight(.bold))
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(EvilifeTheme.boundary.opacity(0.12), in: Capsule())
                    .foregroundStyle(EvilifeTheme.boundary)
            }
        }
    }
}

struct CrisisCardView: View {
    let module: ModulePlanItem

    var body: some View {
        CardShell(tint: EvilifeTheme.crisis, icon: "heart.text.square.fill") {
            if let title = module.props["title"]?.string {
                Text(title).font(.subheadline.weight(.semibold))
            }
            if let message = module.props["message"]?.string {
                Text(message).font(.footnote).fixedSize(horizontal: false, vertical: true)
            }
            let steps = module.props["immediate_steps"]?.stringArray ?? []
            if !steps.isEmpty {
                ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                    Text("\(index + 1). \(step)").font(.caption)
                }
            }
            if let note = module.props["supportive_note"]?.string {
                Text(note).font(.caption).foregroundStyle(EvilifeTheme.textSecondary)
            }
            let avoid = module.props["avoid_actions"]?.stringArray ?? []
            if !avoid.isEmpty {
                Text("请暂时不要：\(avoid.joined(separator: "、"))")
                    .font(.caption).foregroundStyle(EvilifeTheme.textSecondary)
            }
            let contacts = module.props["emergency_contacts"]?.array ?? []
            if !contacts.isEmpty {
                ForEach(contacts.indices, id: \.self) { index in
                    let contact = contacts[index].object ?? [:]
                    if let name = contact["name"]?.string, let phone = contact["phone"]?.string {
                        HStack(spacing: 6) {
                            Text("\(name)：\(phone)")
                                .font(.caption.weight(.medium))
                            Spacer()
                            Link("拨打", destination: URL(string: "tel:\(phone)")!)
                                .font(.caption.weight(.semibold))
                        }
                        .padding(8)
                        .background(EvilifeTheme.crisis.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
                    }
                }
            }
        }
    }
}

struct ClarificationCardView: View {
    let module: ModulePlanItem
    let onSelect: (String) -> Void

    var body: some View {
        CardShell(tint: EvilifeTheme.partly, icon: "questionmark.bubble.fill") {
            if let question = module.props["question"]?.string {
                Text(question).font(.subheadline.weight(.semibold))
            }
            let options = module.props["options"]?.array ?? []
            ForEach(options.indices, id: \.self) { index in
                let option = options[index].object ?? [:]
                if let value = option["value"]?.string {
                    Button {
                        onSelect(value)
                    } label: {
                        HStack {
                            Text(option["label"]?.string ?? value)
                                .font(.footnote)
                            Spacer()
                            Image(systemName: "arrow.up.circle")
                                .font(.footnote)
                        }
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(EvilifeTheme.pageBg, in: RoundedRectangle(cornerRadius: 10))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}

// MARK: - HealthRecordDraft

struct DraftItem: Identifiable {
    let id: String
    let kind: String
    let label: String
    let unit: String
    var value: Double
    let sourceText: String
}

struct HealthRecordDraftCard: View {
    let module: ModulePlanItem
    @State private var drafts: [DraftItem] = []
    @State private var saving = false
    @State private var savedCount = 0
    @State private var errorMessage = ""

    var body: some View {
        CardShell(tint: EvilifeTheme.brand, icon: "list.clipboard.fill") {
            if savedCount > 0 {
                Label("已添加 \(savedCount) 条健康记录", systemImage: "checkmark.circle.fill")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(EvilifeTheme.brand)
            } else {
                Text("发现可添加的健康记录（来自你的描述，非 AI 测量值）。确认前不会写入健康档案。")
                    .font(.caption)
                    .foregroundStyle(EvilifeTheme.textSecondary)
                ForEach($drafts) { $draft in
                    HStack(spacing: 8) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(draft.label).font(.footnote.weight(.medium))
                            if !draft.sourceText.isEmpty {
                                Text("来自「\(draft.sourceText)」")
                                    .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                                    .lineLimit(1)
                            }
                        }
                        Spacer()
                        TextField("数值", value: $draft.value, format: .number)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                            .frame(width: 90)
                            .padding(.horizontal, 8).padding(.vertical, 6)
                            .background(EvilifeTheme.pageBg, in: RoundedRectangle(cornerRadius: 8))
                        Text(draft.unit).font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                    }
                }
                if !errorMessage.isEmpty {
                    Text(errorMessage).font(.caption).foregroundStyle(EvilifeTheme.riskRefused)
                }
                Button {
                    Task { await save() }
                } label: {
                    if saving {
                        ProgressView().frame(maxWidth: .infinity)
                    } else {
                        Text("确认并添加（\(drafts.count) 条）").frame(maxWidth: .infinity)
                    }
                }
                .buttonStyle(.borderedProminent)
                .tint(EvilifeTheme.brand)
                .disabled(saving || drafts.isEmpty)
            }
        }
        .onAppear { loadDrafts() }
    }

    private func loadDrafts() {
        let items = module.props["items"]?.array ?? []
        drafts = items.compactMap { item in
            let object = item.object ?? [:]
            guard let id = object["id"]?.string,
                  let kind = object["kind"]?.string,
                  let value = object["value"]?.double else { return nil }
            return DraftItem(
                id: id,
                kind: kind,
                label: object["label"]?.string ?? observationKindLabel(kind),
                unit: object["unit"]?.string ?? observationUnit(kind),
                value: value,
                sourceText: object["source_text"]?.string ?? "")
        }
    }

    private func save() async {
        saving = true
        errorMessage = ""
        defer { saving = false }
        do {
            let records = try await API.addObservations(
                drafts.map { ObservationCreate(kind: $0.kind, value: $0.value, source: "self_report") })
            savedCount = records.count
        } catch {
            errorMessage = "记录没有写入：\(error.localizedDescription)"
        }
    }
}

// MARK: - MealAnalyzer

struct MealAnalyzerCard: View {
    let module: ModulePlanItem
    @State private var saving = false
    @State private var saved = false
    @State private var errorMessage = ""

    var body: some View {
        CardShell(tint: .orange, icon: "fork.knife") {
            if saved {
                Label("餐食记录已保存", systemImage: "checkmark.circle.fill")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(EvilifeTheme.brand)
            } else {
                if let error = module.props["analysis_error"]?.string, !error.isEmpty {
                    Text("识别未完成：\(error)").font(.footnote).foregroundStyle(EvilifeTheme.riskRefused)
                } else {
                    let items = module.props["items"]?.array ?? []
                    ForEach(items.indices, id: \.self) { index in
                        let item = items[index].object ?? [:]
                        let calories = item["estimated_calories"]?.stringInts ?? []
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item["name"]?.string ?? "未命名食物")
                                    .font(.footnote.weight(.medium))
                                Text(item["portion"]?.string ?? "")
                                    .font(.caption2).foregroundStyle(EvilifeTheme.textSecondary)
                            }
                            Spacer()
                            if calories.count == 2 {
                                Text("\(calories[0])–\(calories[1]) kcal")
                                    .font(.caption.weight(.medium))
                            }
                        }
                    }
                    if let total = module.props["total_calories"]?.stringInts, total.count == 2 {
                        HStack {
                            Text("合计估算").font(.footnote.weight(.semibold))
                            Spacer()
                            Text("\(total[0])–\(total[1]) kcal").font(.footnote.weight(.semibold))
                        }
                        .padding(.top, 4)
                    }
                    if let uncertainty = module.props["overall_uncertainty"]?.string, !uncertainty.isEmpty {
                        Text("估算不确定性：\(uncertainty)")
                            .font(.caption2).foregroundStyle(EvilifeTheme.textTertiary)
                    }
                    if !errorMessage.isEmpty {
                        Text(errorMessage).font(.caption).foregroundStyle(EvilifeTheme.riskRefused)
                    }
                    Button {
                        Task { await confirm() }
                    } label: {
                        if saving {
                            ProgressView().frame(maxWidth: .infinity)
                        } else {
                            Text("确认并保存餐食记录").frame(maxWidth: .infinity)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.orange)
                    .disabled(saving)
                }
            }
        }
    }

    private func confirm() async {
        saving = true
        errorMessage = ""
        defer { saving = false }
        let actionId = module.props["action_id"]?.string ?? ""
        guard !actionId.isEmpty else {
            errorMessage = "缺少 action_id，无法确认。"
            return
        }
        struct ConfirmItem: Encodable {
            let id: String, name: String, portion: String
            let portion_grams: [Int]?
            let estimated_calories: [Int]
            let estimated_calories_center: Int?
            let confidence: String?, reference_basis: String?, uncertainty: String?
        }
        struct ConfirmBody: Encodable {
            let run_id: String, confirmed: Bool, client_action_id: String
            let edited_items: [ConfirmItem]
            let estimated_total_calories: [Int]
            let estimated_total_calories_center: Int?
        }
        let rawItems = module.props["items"]?.array ?? []
        let edited = rawItems.compactMap { raw -> ConfirmItem? in
            let object = raw.object ?? [:]
            guard let id = object["id"]?.string,
                  let name = object["name"]?.string,
                  let calories = object["estimated_calories"]?.stringInts, calories.count == 2
            else { return nil }
            let center = object["estimated_calories_center"]?.int
            return ConfirmItem(
                id: id, name: name,
                portion: object["portion"]?.string ?? "",
                portion_grams: object["portion_grams"]?.stringInts,
                estimated_calories: calories,
                estimated_calories_center: center,
                confidence: object["confidence"]?.string,
                reference_basis: object["reference_basis"]?.string,
                uncertainty: object["uncertainty"]?.string)
        }
        let total = module.props["total_calories"]?.stringInts ?? [0, 0]
        let totalCenter = module.props["total_calories_center"]?.int
        let body = ConfirmBody(
            run_id: "current-run", confirmed: true, client_action_id: actionId,
            edited_items: edited,
            estimated_total_calories: total,
            estimated_total_calories_center: totalCenter)
        do {
            let data = try await APIClient.shared.post("/api/v1/actions/\(actionId)/confirm", json: body)
            if let dict = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let status = dict["status"] as? String {
                saved = status == "completed"
                if !saved { errorMessage = "保存未完成（\(status)）。" }
            }
        } catch {
            errorMessage = "保存失败：\(error.localizedDescription)"
        }
    }
}

// MARK: - FastingTimer / DocumentSummary / FeaturePanel

struct FastingTimerCard: View {
    let module: ModulePlanItem

    var body: some View {
        CardShell(tint: .purple, icon: "timer") {
            Text("禁食计时")
                .font(.subheadline.weight(.semibold))
            Text("打开「今日」标签页即可开始 16:8 禁食计时，或记录饮水、步数等日常指标。")
                .font(.footnote).foregroundStyle(EvilifeTheme.textSecondary)
        }
    }
}

struct DocumentSummaryCard: View {
    let module: ModulePlanItem

    var body: some View {
        CardShell(tint: .indigo, icon: "doc.plaintext.fill") {
            if let name = module.props["document_name"]?.string {
                Text(name).font(.subheadline.weight(.semibold))
            }
            if let summary = module.props["one_sentence_summary"]?.string {
                Text(summary).font(.footnote).fixedSize(horizontal: false, vertical: true)
            }
            let points = module.props["key_points"]?.stringArray ?? []
            if !points.isEmpty {
                ForEach(points, id: \.self) { point in
                    Text("• \(point)").font(.caption)
                }
            }
            let claims = module.props["detailed_claims"]?.array ?? []
            if !claims.isEmpty {
                ForEach(claims.indices, id: \.self) { index in
                    if let text = claims[index].object?["claim"]?.string {
                        Text("\(index + 1). \(text)").font(.caption)
                    }
                }
            }
        }
    }
}

struct ChatFeaturePanelCard: View {
    let module: ModulePlanItem

    var body: some View {
        CardShell(tint: EvilifeTheme.partly, icon: "wand.and.stars") {
            Text(module.props["title"]?.string ?? "功能建议")
                .font(.subheadline.weight(.semibold))
            Text("你可以在「今日」与「健康」标签页使用相关功能。")
                .font(.footnote).foregroundStyle(EvilifeTheme.textSecondary)
        }
    }
}

struct UnknownModuleCard: View {
    let module: ModulePlanItem

    var body: some View {
        CardShell(tint: EvilifeTheme.textTertiary, icon: "questionmark.square.dashed") {
            Text("模块：\(module.type)")
                .font(.caption.weight(.semibold))
                .foregroundStyle(EvilifeTheme.textTertiary)
        }
    }
}
