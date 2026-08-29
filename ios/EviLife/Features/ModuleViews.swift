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
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(tint)
                Text(iconTitle)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(tint)
                Spacer()
            }
            content
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(EvilifeTheme.cardBg, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(tint.opacity(0.18), lineWidth: 1))
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
        case "wand.and.stars": return "相关功能"
        case "questionmark.square.dashed": return "内容"
        default: return "证据答案"
        }
    }
}

// MARK: - EvidenceAnswer

struct EvidenceAnswerCard: View {
    let module: ModulePlanItem
    @State private var detailsExpanded = false

    private var props: [String: JSONValue] { module.props }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
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
                Spacer()
            }

            if let conclusion = props["conclusion"]?.string {
                Text(conclusion)
                    .font(.body.weight(.semibold))
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let verdict = props["verdict"]?.object {
                VerdictView(verdict: verdict, detailsExpanded: detailsExpanded)
            }

            let advice = props["general_advice"]?.stringArray ?? []
            if !advice.isEmpty {
                section("行动建议") {
                    ForEach(Array(advice.prefix(2)), id: \.self) { item in
                        bullet("arrow.right.circle.fill", color: EvilifeTheme.brand, item)
                    }
                }
            }

            if hasDetails {
                Button {
                    withAnimation(.easeOut(duration: 0.2)) { detailsExpanded.toggle() }
                } label: {
                    HStack(spacing: 6) {
                        Text(detailsExpanded ? "收起" : detailsLabel)
                        Image(systemName: "chevron.down")
                            .font(.caption2)
                            .rotationEffect(.degrees(detailsExpanded ? 180 : 0))
                    }
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(EvilifeTheme.brandDark)
                }
                .buttonStyle(.plain)

                if detailsExpanded {
                    if let explanation = props["explanation"]?.string, !explanation.isEmpty {
                        section("解释") {
                            Text(explanation).font(.footnote).fixedSize(horizontal: false, vertical: true)
                        }
                    }

                    let target = props["target_population"]?.stringArray ?? []
                    let nonTarget = props["non_target_population"]?.stringArray ?? []
                    if !target.isEmpty || !nonTarget.isEmpty {
                        section("适用范围") {
                            ForEach(target, id: \.self) { item in
                                bullet("checkmark.circle.fill", color: EvilifeTheme.supported, item)
                            }
                            ForEach(nonTarget, id: \.self) { item in
                                bullet("xmark.circle.fill", color: EvilifeTheme.partly, item)
                            }
                        }
                    }

                    if advice.count > 2 {
                        section("更多建议") {
                            ForEach(Array(advice.dropFirst(2)), id: \.self) { item in
                                bullet("arrow.right.circle.fill", color: EvilifeTheme.brand, item)
                            }
                        }
                    }

                    let limitations = props["limitations"]?.stringArray ?? []
                    if !limitations.isEmpty {
                        section("边界") {
                            ForEach(limitations, id: \.self) { item in
                                bullet("exclamationmark.triangle.fill", color: EvilifeTheme.boundary, item)
                            }
                        }
                    }

                    if let tcm = props["tcm_perspective"]?.object {
                        section("中医视角") {
                            ForEach(Array(tcm.keys.sorted()), id: \.self) { key in
                                if let value = tcm[key], !value.isNull, !value.displayText.isEmpty {
                                    Text(value.displayText).font(.footnote)
                                }
                            }
                        }
                    }

                    if let citations = props["citations"]?.array, !citations.isEmpty {
                        CitationsView(citations: citations)
                    }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(EvilifeTheme.cardBg, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(EvilifeTheme.brand.opacity(0.2), lineWidth: 1))
    }

    private var detailsLabel: String {
        let count = props["citations"]?.array?.count ?? 0
        return count > 0 ? "详情 · 来源 \(count)" : "详情"
    }

    private var hasDetails: Bool {
        let explanation = props["explanation"]?.string ?? ""
        return !explanation.isEmpty
            || !(props["target_population"]?.stringArray ?? []).isEmpty
            || !(props["non_target_population"]?.stringArray ?? []).isEmpty
            || (props["general_advice"]?.stringArray ?? []).count > 2
            || !(props["limitations"]?.stringArray ?? []).isEmpty
            || props["tcm_perspective"]?.object != nil
            || !(props["citations"]?.array ?? []).isEmpty
            || verdictHasDetails
    }

    private var verdictHasDetails: Bool {
        guard let verdict = props["verdict"]?.object else { return false }
        return !(verdict["claim"]?.string ?? "").isEmpty
            || !(verdict["supporting_evidence"]?.array ?? []).isEmpty
            || !(verdict["opposing_evidence"]?.array ?? []).isEmpty
            || !(verdict["applies_to"]?.stringArray ?? []).isEmpty
            || !(verdict["does_not_apply_to"]?.stringArray ?? []).isEmpty
            || !(verdict["uncertainty"]?.stringArray ?? []).isEmpty
            || !(verdict["what_could_change_this_verdict"]?.stringArray ?? []).isEmpty
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
    let detailsExpanded: Bool

    private var value: String { verdict["verdict"]?.string ?? "insufficient" }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                Text(verdictLabel(value))
                    .font(.headline)
                    .foregroundStyle(verdictColor(value))
                if let confidence = verdict["confidence"]?.double {
                    Text("\(Int((confidence * 100).rounded()))%")
                        .font(.caption)
                        .foregroundStyle(EvilifeTheme.textSecondary)
                }
                Spacer()
            }
            if let reason = verdict["short_reason"]?.string {
                Text(reason).font(.footnote).foregroundStyle(EvilifeTheme.textSecondary)
            }

            if detailsExpanded {
                if let claim = verdict["claim"]?.string, !claim.isEmpty {
                    Text(claim)
                        .font(.caption)
                        .foregroundStyle(EvilifeTheme.textTertiary)
                }
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
                        Text("可能改变结论").font(.caption.weight(.semibold)).foregroundStyle(EvilifeTheme.textSecondary)
                        ForEach(couldChange, id: \.self) { item in
                            Text("• \(item)").font(.caption)
                        }
                    }
                }
            }
        }
        .padding(.vertical, 2)
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

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "link")
                    .font(.caption)
                Text("来源 \(citations.count)")
                    .font(.caption.weight(.semibold))
            }
            .foregroundStyle(EvilifeTheme.brandDark)

            ForEach(citations.indices, id: \.self) { index in
                let citation = citations[index].object ?? [:]
                VStack(alignment: .leading, spacing: 3) {
                    Text("\(citation["evidence_id"]?.string ?? "E\(index + 1)") · \(citation["title"]?.string ?? "未命名来源")")
                        .font(.caption.weight(.medium))
                    HStack(spacing: 6) {
                        if let year = citation["year"]?.int {
                            Text(String(year)).font(.caption2)
                        }
                        if let org = citation["organization"]?.string {
                            Text(org).font(.caption2).lineLimit(1)
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
                .padding(.vertical, 3)
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
                DisclosureGroup("边界") {
                    ForEach(limitations, id: \.self) { item in
                        Text(item)
                    }
                }
                .font(.caption2)
                .foregroundStyle(EvilifeTheme.textTertiary)
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
                Text("确认后写入健康档案。")
                    .font(.caption)
                    .foregroundStyle(EvilifeTheme.textSecondary)
                ForEach($drafts) { $draft in
                    HStack(spacing: 8) {
                        Text(draft.label).font(.footnote.weight(.medium))
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
                        Text("添加 \(drafts.count) 条").frame(maxWidth: .infinity)
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
                value: value)
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
                        Text("估算：\(uncertainty)")
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
                            Text("保存记录").frame(maxWidth: .infinity)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(EvilifeTheme.brand)
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
        CardShell(tint: EvilifeTheme.brand, icon: "timer") {
            Text("去「今日」开始计时。")
                .font(.footnote).foregroundStyle(EvilifeTheme.textSecondary)
        }
    }
}

struct DocumentSummaryCard: View {
    let module: ModulePlanItem

    var body: some View {
        CardShell(tint: EvilifeTheme.brand, icon: "doc.plaintext.fill") {
            if let name = module.props["document_name"]?.string {
                Text(name).font(.subheadline.weight(.semibold))
            }
            if let summary = module.props["one_sentence_summary"]?.string {
                Text(summary).font(.footnote).fixedSize(horizontal: false, vertical: true)
            }
            let points = module.props["key_points"]?.stringArray ?? []
            let claims = module.props["detailed_claims"]?.array ?? []
            if !points.isEmpty || !claims.isEmpty {
                DisclosureGroup("详情") {
                    ForEach(points, id: \.self) { point in
                        Text(point).font(.caption)
                    }
                    ForEach(claims.indices, id: \.self) { index in
                        if let text = claims[index].object?["claim"]?.string {
                            Text(text).font(.caption)
                        }
                    }
                }
                .font(.caption)
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
            Text("前往「今日」或「健康」。")
                .font(.footnote).foregroundStyle(EvilifeTheme.textSecondary)
        }
    }
}

struct UnknownModuleCard: View {
    let module: ModulePlanItem

    var body: some View {
        CardShell(tint: EvilifeTheme.textTertiary, icon: "questionmark.square.dashed") {
            Text("暂无法显示此内容")
                .font(.caption.weight(.semibold))
                .foregroundStyle(EvilifeTheme.textTertiary)
        }
    }
}
