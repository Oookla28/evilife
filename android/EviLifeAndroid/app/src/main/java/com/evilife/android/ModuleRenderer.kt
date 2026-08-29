package com.evilife.android

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

@Composable
fun ModuleRenderer(
    modules: List<ModulePlanItem>,
    api: Api,
    onClarification: (String) -> Unit,
) {
    if (modules.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
        modules.forEach { module ->
            ModuleCard(module = module, api = api, onClarification = onClarification)
        }
    }
}

@Composable
private fun ModuleCard(module: ModulePlanItem, api: Api, onClarification: (String) -> Unit) {
    when (module.type) {
        "EvidenceAnswer", "EvidenceFlow" -> EvidenceAnswerCard(module)
        "SafetyCard" -> SafetyModuleCard(module)
        "GeneralAnswerCard" -> GeneralAnswerModuleCard(module)
        "CrisisSupportCard", "ExtremeCrisisCareCard" -> CrisisModuleCard(module)
        "ClarificationCard" -> ClarificationModuleCard(module, onClarification)
        "HealthRecordDraft" -> HealthRecordDraftCard(module, api)
        "MealAnalyzer" -> MealAnalyzerCard(module, api)
        "DocumentSummary" -> DocumentSummaryCard(module)
        "FastingTimer" -> FastingModuleCard(module)
        "ChatFeaturePanel" -> FeatureModuleCard(module)
        else -> UnknownModuleCard(module)
    }
}

@Composable
private fun ModuleShell(
    title: String,
    subtitle: String? = null,
    color: Color = MaterialTheme.colorScheme.primary,
    content: @Composable ColumnScope.() -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, color = color)
            subtitle?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            content()
        }
    }
}

@Composable
private fun EvidenceAnswerCard(module: ModulePlanItem) {
    val props = module.props
    var expanded by remember(module.moduleId) { mutableStateOf(false) }
    val conclusion = props.text("conclusion") ?: "正在生成结论"
    val gate = props.text("gate_status") ?: "normal"
    val strength = props.text("evidence_strength") ?: "insufficient"
    val verdict = props.optJSONObject("verdict")
    val verdictLabel = verdict?.let { verdictLabel(it.text("verdict")) }
    ModuleShell(
        title = conclusion,
        subtitle = props.text("explanation"),
        color = when (gate) {
            "refused" -> Color(0xFFB42318)
            "degraded" -> Color(0xFF9A6700)
            else -> MaterialTheme.colorScheme.primary
        },
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            StatusPill(if (gate == "normal") "正常" else if (gate == "degraded") "证据受限" else "已限制", gateColor(gate))
            StatusPill(strengthLabel(strength), strengthColor(strength))
            verdictLabel?.let { StatusPill("裁决：$it", Color(0xFF2F6F63)) }
        }
        verdict?.let {
            Text(it.text("claim") ?: "", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
            Text(it.text("short_reason") ?: "", style = MaterialTheme.typography.bodySmall)
        }
        val advice = props.strings("general_advice")
        if (advice.isNotEmpty()) {
            Text("建议", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
            advice.take(if (expanded) advice.size else 3).forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }
        }
        if (expanded) {
            val target = props.strings("target_population")
            val nonTarget = props.strings("non_target_population")
            val limits = props.strings("limitations")
            if (target.isNotEmpty()) DetailList("适用人群", target)
            if (nonTarget.isNotEmpty()) DetailList("不适用边界", nonTarget)
            if (limits.isNotEmpty()) DetailList("不确定性与局限", limits)
            verdict?.let {
                EvidenceList("支持证据", it.optJSONArray("supporting_evidence"), Color(0xFF2F7D68))
                EvidenceList("反对或边界证据", it.optJSONArray("opposing_evidence"), Color(0xFF9A6700))
                DetailList("裁决不确定性", it.strings("uncertainty"))
            }
            CitationList(props.optJSONArray("citations"))
        }
        TextButton(onClick = { expanded = !expanded }, modifier = Modifier.align(Alignment.End)) {
            Text(if (expanded) "收起证据详情" else "展开证据、边界与引用")
        }
    }
}

@Composable
private fun SafetyModuleCard(module: ModulePlanItem) {
    val props = module.props
    ModuleShell(props.text("title") ?: "安全提示", color = Color(0xFFB42318)) {
        Text(props.text("message") ?: "当前问题需要专业人员进一步评估。", style = MaterialTheme.typography.bodySmall)
        StatusPill(if (props.text("severity") == "high") "高风险边界" else "谨慎处理", Color(0xFFB42318))
    }
}

@Composable
private fun GeneralAnswerModuleCard(module: ModulePlanItem) {
    val props = module.props
    ModuleShell(props.text("title") ?: "通用问题回答", props.text("classification_reason"), Color(0xFF3479C6)) {
        Text(props.text("answer") ?: "", style = MaterialTheme.typography.bodyMedium)
        DetailList("要点", props.strings("key_points"))
        DetailList("边界", props.strings("limitations"))
        props.text("boundary_label")?.let { StatusPill(it, Color(0xFF7A641D)) }
    }
}

@Composable
private fun CrisisModuleCard(module: ModulePlanItem) {
    val props = module.props
    val imminent = props.text("crisis_level") == "imminent" || module.type == "ExtremeCrisisCareCard"
    ModuleShell(
        props.text("title") ?: "先照顾此刻的安全",
        props.text("message"),
        if (imminent) Color(0xFFB42318) else Color(0xFF287E75),
    ) {
        props.text("check_in_question")?.let { Text(it, fontWeight = FontWeight.SemiBold) }
        props.strings("reply_options").takeIf { it.isNotEmpty() }?.let { options ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { options.forEach { StatusPill(it, Color(0xFF287E75)) } }
        }
        props.strings("immediate_steps").forEachIndexed { index, item -> Text("${index + 1}. $item", style = MaterialTheme.typography.bodySmall) }
        props.text("reach_out_message")?.let { Text("可以直接发给身边的人：\n$it", style = MaterialTheme.typography.bodySmall) }
        props.strings("emergency_contacts").forEach { Text(it, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold) }
        props.strings("avoid_actions").takeIf { it.isNotEmpty() }?.let { DetailList("此刻先避免", it) }
        props.text("supportive_note")?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

@Composable
private fun ClarificationModuleCard(module: ModulePlanItem, onClarification: (String) -> Unit) {
    val props = module.props
    ModuleShell(props.text("question") ?: "请补充更多信息", color = Color(0xFF7A641D)) {
        val options = props.optJSONArray("options")
        if (options == null || options.length() == 0) Text("请直接补充相关情况后再发送。", style = MaterialTheme.typography.bodySmall)
        else for (index in 0 until options.length()) {
            val option = options.optJSONObject(index)
            val label = option?.text("label") ?: option?.text("value") ?: continue
            val value = option.text("value") ?: label
            OutlinedButton(onClick = { onClarification(value) }, modifier = Modifier.fillMaxWidth()) { Text(label, maxLines = 2, overflow = TextOverflow.Ellipsis) }
        }
        Text("选择后会填入输入框，请确认内容再发送。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

private data class DraftState(val id: String, val kind: String, val label: String, val unit: String, val source: String, val value: String)

@Composable
private fun HealthRecordDraftCard(module: ModulePlanItem, api: Api) {
    val scope = rememberCoroutineScope()
    var drafts by remember(module.moduleId) { mutableStateOf(parseDrafts(module.props)) }
    var state by remember(module.moduleId) { mutableStateOf("") }
    var saving by remember(module.moduleId) { mutableStateOf(false) }
    ModuleShell("发现可添加的健康记录", "请核对或修改数值。确认前不会写入健康档案。", Color(0xFF0F766E)) {
        drafts.forEach { draft ->
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(draft.label, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                    if (draft.source.isNotBlank()) Text("来自：${draft.source}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                OutlinedTextField(
                    value = draft.value,
                    onValueChange = { value -> drafts = drafts.map { if (it.id == draft.id) it.copy(value = value) else it } },
                    modifier = Modifier.width(110.dp),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    label = { Text(draft.unit) },
                )
            }
        }
        Button(onClick = {
            val values = drafts.mapNotNull { draft -> draft.value.toDoubleOrNull()?.let { ObservationDraft(draft.kind, it) } }
            if (values.size != drafts.size) { state = "请先填写有效数值"; return@Button }
            saving = true
            scope.launch {
                runCatching { api.addObservationsBatch(values) }
                    .onSuccess { state = "已确认并添加 ${it.size} 条健康记录" }
                    .onFailure { state = it.displayMessage("记录没有写入") }
                saving = false
            }
        }, enabled = drafts.isNotEmpty() && !saving, modifier = Modifier.fillMaxWidth()) { Text(if (saving) "保存中..." else "确认并添加") }
        if (state.isNotBlank()) Text(state, style = MaterialTheme.typography.bodySmall, color = if (state.contains("失败") || state.contains("没有") || state.contains("有效")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
    }
}

@Composable
private fun MealAnalyzerCard(module: ModulePlanItem, api: Api) {
    val props = module.props
    val scope = rememberCoroutineScope()
    var state by remember(module.moduleId) { mutableStateOf("") }
    var saving by remember(module.moduleId) { mutableStateOf(false) }
    ModuleShell("餐食图片识别", "这是估算范围，不是精确测量；确认前不会写入今日记录。", Color(0xFF9A6547)) {
        val items = props.optJSONArray("items")
        if (items == null || items.length() == 0) {
            Text(props.text("analysis_error") ?: "没有识别到可用餐食内容。", style = MaterialTheme.typography.bodySmall)
        } else {
            for (index in 0 until items.length()) {
                val item = items.optJSONObject(index) ?: continue
                val calories = item.intRange("estimated_calories")
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Row(modifier = Modifier.fillMaxWidth()) {
                        Text(item.text("name") ?: "未命名食物", fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
                        if (calories != null) Text("${calories.first}-${calories.second} kcal", style = MaterialTheme.typography.bodySmall)
                    }
                    Text(item.text("portion") ?: "", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            props.intRange("total_calories")?.let { Text("合计估算：${it.first}-${it.second} kcal", fontWeight = FontWeight.SemiBold) }
            Button(onClick = {
                val actionId = props.text("action_id")
                if (actionId.isNullOrBlank()) { state = "缺少 action_id，无法确认"; return@Button }
                saving = true
                scope.launch {
                    val payload = JSONObject().put("run_id", "android-${module.moduleId}").put("confirmed", true).put("client_action_id", actionId)
                    payload.put("edited_items", items)
                    props.intRange("total_calories")?.let { payload.put("estimated_total_calories", JSONArray(listOf(it.first, it.second))) }
                    props.optIntOrNull("total_calories_center")?.let { payload.put("estimated_total_calories_center", it) }
                    runCatching { api.confirmAction(actionId, payload) }
                        .onSuccess { response -> state = if (response.text("status") == "completed") "餐食记录已保存" else "保存状态：${response.text("status") ?: "未知"}" }
                        .onFailure { state = it.displayMessage("餐食记录保存失败") }
                    saving = false
                }
            }, enabled = !saving, modifier = Modifier.fillMaxWidth()) { Text(if (saving) "保存中..." else "确认并保存餐食记录") }
        }
        if (state.isNotBlank()) Text(state, style = MaterialTheme.typography.bodySmall, color = if (state.contains("失败") || state.contains("缺少")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
    }
}

@Composable
private fun DocumentSummaryCard(module: ModulePlanItem) {
    val props = module.props
    var detailed by remember(module.moduleId) { mutableStateOf(false) }
    ModuleShell(props.text("document_name") ?: "文档摘要", props.text("one_sentence_summary"), Color(0xFF4355A5)) {
        if (!detailed) {
            val points = props.optJSONArray("key_points")
            if (points == null || points.length() == 0) Text("暂无结构化要点", style = MaterialTheme.typography.bodySmall)
            else for (index in 0 until points.length()) {
                val point = points.optJSONObject(index)
                Text("• ${(point?.text("title") ?: point?.text("description") ?: points.optString(index))}", style = MaterialTheme.typography.bodySmall)
                point?.text("description")?.let { Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        } else {
            val claims = props.optJSONArray("detailed_claims")
            if (claims == null || claims.length() == 0) Text("暂无详细主张", style = MaterialTheme.typography.bodySmall)
            else for (index in 0 until claims.length()) {
                val claim = claims.optJSONObject(index)
                Text("${index + 1}. ${claim?.text("text") ?: claim?.text("claim") ?: claims.optString(index)}", style = MaterialTheme.typography.bodySmall)
                claim?.optIntOrNull("page_number")?.let { Text("第 ${it} 页", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary) }
            }
        }
        TextButton(onClick = { detailed = !detailed }, modifier = Modifier.align(Alignment.End)) { Text(if (detailed) "查看结构化要点" else "查看详细主张") }
    }
}

@Composable
private fun FastingModuleCard(module: ModulePlanItem) {
    ModuleShell("进食间隔计时", "可前往“今日”标签开始或结束计时；计时只记录时间，不生成医疗建议。", Color(0xFF6A4C93)) {
        module.props.text("message")?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
    }
}

@Composable
private fun FeatureModuleCard(module: ModulePlanItem) {
    val props = module.props
    val title = props.text("title") ?: "功能模块"
    val message = when (props.text("feature")) {
        "health_profile_analysis" -> "可在“健康”标签页查看综合健康档案分析。"
        "today_review" -> "可在“今日”标签页查看当天的健康记录、餐食和进食间隔。"
        "meal_photo" -> "可以上传餐食图片，识别后请核对估算并手动确认保存。"
        "health_connectors" -> "可在“健康”标签页授权并同步系统健康数据。"
        else -> "相关功能已准备好，可从底部标签页继续。"
    }
    ModuleShell(title, message, Color(0xFF7A641D)) { }
}

@Composable
private fun UnknownModuleCard(module: ModulePlanItem) {
    ModuleShell("暂不支持的模块", "系统返回了当前 Android 版本尚未专门渲染的模块。其他内容仍可继续使用。", Color(0xFF667085)) {
        Text(module.type, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun StatusPill(text: String, color: Color) {
    Text(text, modifier = Modifier.padding(horizontal = 9.dp, vertical = 4.dp), style = MaterialTheme.typography.labelSmall, color = color, fontWeight = FontWeight.SemiBold)
}

@Composable
private fun DetailList(title: String, items: List<String>) {
    if (items.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(title, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
        items.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }
    }
}

@Composable
private fun EvidenceList(title: String, items: JSONArray?, color: Color) {
    if (items == null || items.length() == 0) return
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(title, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold, color = color)
        for (index in 0 until items.length()) {
            val item = items.optJSONObject(index) ?: continue
            Text("• ${item.text("title") ?: item.text("finding") ?: "证据"}", style = MaterialTheme.typography.bodySmall)
            item.text("finding")?.let { Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}

@Composable
private fun CitationList(items: JSONArray?) {
    if (items == null || items.length() == 0) return
    val uriHandler = LocalUriHandler.current
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text("引用来源", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
        for (index in 0 until items.length()) {
            val item = items.optJSONObject(index) ?: continue
            val title = item.text("title") ?: "来源 ${index + 1}"
            val url = item.text("url")
            if (url.isNullOrBlank()) Text("${index + 1}. $title", style = MaterialTheme.typography.bodySmall)
            else TextButton(onClick = { runCatching { uriHandler.openUri(url) } }, contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)) { Text("${index + 1}. $title", maxLines = 2, overflow = TextOverflow.Ellipsis) }
        }
    }
}

private fun parseDrafts(props: JSONObject): List<DraftState> {
    val items = props.optJSONArray("items") ?: return emptyList()
    return (0 until items.length()).mapNotNull { index ->
        val item = items.optJSONObject(index) ?: return@mapNotNull null
        DraftState(item.text("id") ?: "draft-$index", item.text("kind") ?: return@mapNotNull null, item.text("label") ?: item.text("kind") ?: "记录", item.text("unit") ?: "", item.text("source_text") ?: "", item.optString("value"))
    }
}

private fun JSONObject.text(key: String): String? = optString(key).takeIf { it.isNotBlank() && it != "null" }

private fun JSONObject.strings(key: String): List<String> {
    val array = optJSONArray(key) ?: return emptyList()
    return (0 until array.length()).mapNotNull { index ->
        when (val value = array.opt(index)) {
            is JSONObject -> value.text("label") ?: value.text("value") ?: value.text("title")
                ?: value.text("name")?.let { name -> value.text("number")?.let { "$name：$it" } ?: value.text("phone")?.let { "$name：$it" } ?: name }
            else -> value?.toString()?.takeIf { it.isNotBlank() && it != "null" }
        }
    }
}

private fun JSONObject.intRange(key: String): Pair<Int, Int>? {
    val array = optJSONArray(key) ?: return null
    if (array.length() < 2) return null
    val low = array.optInt(0, Int.MIN_VALUE)
    val high = array.optInt(1, Int.MIN_VALUE)
    return if (low == Int.MIN_VALUE || high == Int.MIN_VALUE) null else low to high
}

private fun JSONObject.optIntOrNull(key: String): Int? = if (has(key) && !isNull(key)) optInt(key) else null

private fun verdictLabel(value: String?): String = when (value) {
    "true" -> "是"
    "partly_true" -> "部分正确"
    "false" -> "否"
    else -> "证据不足"
}

private fun strengthLabel(value: String): String = when (value) {
    "high" -> "高质量证据"
    "medium" -> "中等证据"
    "low" -> "低质量证据"
    else -> "证据不足"
}

private fun strengthColor(value: String): Color = when (value) {
    "high" -> Color(0xFF2F7D68)
    "medium" -> Color(0xFF0F766E)
    "low" -> Color(0xFF9A6700)
    else -> Color(0xFFB42318)
}

private fun gateColor(value: String): Color = when (value) {
    "normal" -> Color(0xFF2F7D68)
    "degraded" -> Color(0xFF9A6700)
    else -> Color(0xFFB42318)
}

private fun Throwable.displayMessage(fallback: String): String = message?.takeIf { it.isNotBlank() } ?: fallback
