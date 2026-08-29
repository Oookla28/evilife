package com.evilife.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.TextButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.health.connect.client.PermissionController
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.Instant
import java.time.LocalDate
import java.util.UUID
import android.provider.OpenableColumns

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { EviLifeApp(Api(this)) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EviLifeApp(api: Api) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val health = remember(context) { HealthSync(context, api) }
    var tab by remember { mutableIntStateOf(0) }
    var user by remember { mutableStateOf<User?>(null) }
    var status by remember { mutableStateOf("正在检查登录状态...") }
    var question by remember { mutableStateOf("") }
    var responseMode by remember { mutableStateOf("life") }
    var attachment by remember { mutableStateOf<Attachment?>(null) }
    var pickerPurpose by remember { mutableStateOf("question") }
    var reportStatus by remember { mutableStateOf("") }
    var sessionId by remember { mutableStateOf(UUID.randomUUID().toString()) }
    val messages = remember { mutableStateListOf<ConversationMessage>() }
    val history = remember { mutableStateListOf<Conversation>() }

    LaunchedEffect(api) {
        user = runCatching { api.currentUser() }.getOrNull()
        status = if (user == null) "" else "已恢复登录状态"
    }
    LaunchedEffect(user?.id) {
        if (user != null) runCatching { api.listConversations() }.onSuccess {
            history.clear()
            history.addAll(it)
        }
    }

    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        result.contents?.let { rawCode ->
            scope.launch {
                status = try {
                    user = api.claimPairing(rawCode)
                    "配对成功，已绑定网页账号"
                } catch (error: Exception) {
                    error.userMessage("配对失败")
                }
            }
        }
    }
    val permissions = rememberLauncherForActivityResult(
        PermissionController.createRequestPermissionResultContract(),
    ) { granted ->
        if (!granted.containsAll(health.permissions)) status = "未获得所需健康权限"
        else scope.launch {
            status = try {
                health.sync()
                "健康数据已同步"
            } catch (error: Exception) {
                error.userMessage("同步失败")
            }
        }
    }
    val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        scope.launch {
            val selected = readAttachment(context, uri) ?: run {
                status = "无法读取文件，或文件超过大小限制"
                return@launch
            }
            if (pickerPurpose == "report") {
                reportStatus = "正在上传并分析报告..."
                reportStatus = runCatching { api.analyzeReport(selected) }
                    .fold(
                        onSuccess = { result -> "${result.fileName}\n${result.summary}" },
                        onFailure = { error -> error.userMessage("报告分析失败") },
                    )
            } else {
                attachment = selected
            }
        }
    }

    MaterialTheme(colorScheme = lightColorScheme(primary = Color(0xFF0F766E), secondary = Color(0xFF14B8A6))) {
        Scaffold(
            containerColor = Color(0xFFF7FAF8),
            topBar = {
                TopAppBar(
                    title = {
                        Column(verticalArrangement = Arrangement.spacedBy(1.dp)) {
                            Text("EviLife", fontWeight = FontWeight.SemiBold)
                            Text(
                                if (user == null) "健康信息整理与循证支持" else "你的健康工作台",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = Color(0xFFF7FAF8)),
                )
            },
            bottomBar = {
                if (user != null) NavigationBar(containerColor = Color.White) {
                    val labels = if (user == null) listOf("登录") else listOf("问答", "历史", "今日", "健康", "设置")
                    labels.forEachIndexed { index, label ->
                        NavigationBarItem(
                            selected = tab == index,
                            onClick = { tab = index },
                            icon = { Text(listOf("⌂", "≡", "日", "♥", "⚙")[index]) },
                            label = { Text(label) },
                        )
                    }
                }
            },
        ) { padding ->
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                verticalArrangement = Arrangement.Top,
            ) {
                val activeUser = user
                if (activeUser == null) {
                    LoginPanel(
                        status = status,
                        onSubmit = { creating, name, email, password ->
                            scope.launch {
                                status = if (creating) "正在创建账号..." else "正在登录..."
                                try {
                                    user = if (creating) api.register(email, password, name) else api.login(email, password)
                                    tab = 0
                                    status = if (creating) "账号创建成功" else "登录成功"
                                } catch (error: Exception) {
                                    status = error.userMessage(if (creating) "注册失败" else "登录失败")
                                }
                            }
                        },
                        onScan = { scanner.launch(ScanOptions().setCaptureActivity(PortraitCaptureActivity::class.java).setOrientationLocked(true).setPrompt("扫描网页上的 EviLife 配对二维码").setBeepEnabled(true)) },
                    )
                } else when (tab) {
                    0 -> QuestionPanel(
                        api = api,
                        question = question,
                        messages = messages,
                        attachment = attachment,
                        responseMode = responseMode,
                        status = status,
                        onPickAttachment = {
                            pickerPurpose = "question"
                            filePicker.launch(arrayOf("image/*", "application/pdf", "text/plain", "text/csv"))
                        },
                        onClearAttachment = { attachment = null },
                        onModeChange = { responseMode = it },
                        onQuestionChange = { question = it },
                        onClarification = { value -> question = value },
                        onAsk = {
                            if (question.isNotBlank() || attachment != null) {
                                val prompt = question.trim()
                                val sentAttachment = attachment
                                question = ""
                                scope.launch {
                                    status = "正在分析..."
                                    try {
                                        val raw = api.orchestrate(sessionId, prompt, responseMode, sentAttachment)
                                        val answer = api.answerText(raw)
                                        val modulePlanRaw = api.modulePlanRaw(raw)
                                        messages.add(ConversationMessage("user-${UUID.randomUUID()}", "user", prompt, fileName = sentAttachment?.name, fileType = sentAttachment?.contentType))
                                        messages.add(ConversationMessage("assistant-${UUID.randomUUID()}", "assistant", answer, modulePlanRaw = modulePlanRaw))
                                        attachment = null
                                        val conversation = Conversation(sessionId, prompt.ifBlank { sentAttachment?.name ?: "附件问答" }.take(120), responseMode, "", messages.toList())
                                        api.saveConversation(conversation)
                                        history.removeAll { it.sessionId == sessionId }
                                        history.add(0, conversation)
                                        status = "回答已生成并同步"
                                    } catch (error: Exception) {
                                        status = error.questionErrorMessage(api.baseUrl)
                                    }
                                }
                            }
                        },
                    )
                    1 -> HistoryPanel(
                        history = history,
                        status = status,
                        onOpen = { conversation ->
                            sessionId = conversation.sessionId
                            messages.clear()
                            messages.addAll(conversation.messages)
                            tab = 0
                            status = "已打开历史对话"
                        },
                        onDelete = { conversation ->
                            scope.launch {
                                try {
                                    api.deleteConversation(conversation.sessionId)
                                    history.removeAll { it.sessionId == conversation.sessionId }
                                    if (conversation.sessionId == sessionId) {
                                        messages.clear()
                                        sessionId = UUID.randomUUID().toString()
                                    }
                                    status = "对话已删除"
                                } catch (error: Exception) {
                                    status = error.userMessage("删除失败")
                                }
                            }
                        },
                    )
                    2 -> TodayPanel(api = api, status = status)
                    3 -> HealthPanel(
                        api = api,
                        reportStatus = reportStatus,
                        onPickReport = {
                            pickerPurpose = "report"
                            filePicker.launch(arrayOf("application/pdf", "text/plain", "text/csv", "image/*"))
                        },
                        status = status,
                        healthAvailable = health.isAvailable(),
                        onRequestPermissions = {
                            if (health.isAvailable()) permissions.launch(health.permissions)
                            else status = "当前设备没有可用的 Health Connect"
                        },
                        onScan = { scanner.launch(ScanOptions().setCaptureActivity(PortraitCaptureActivity::class.java).setOrientationLocked(true).setPrompt("扫描网页上的 EviLife 配对二维码").setBeepEnabled(true)) },
                    )
                    else -> SettingsPanel(
                        api = api,
                        user = activeUser,
                        status = status,
                        onLogout = {
                            scope.launch {
                                runCatching { api.logout() }
                                user = null
                                tab = 0
                                messages.clear()
                                history.clear()
                                status = "已退出登录"
                            }
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun LoginPanel(status: String, onSubmit: (Boolean, String, String, String) -> Unit, onScan: () -> Unit) {
    var creating by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Spacer(Modifier.heightIn(min = 8.dp))
        Text(if (creating) "创建 EviLife 账号" else "登录 EviLife", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
        Text(
            if (creating) "创建后即可在网页和 Android 之间同步对话与健康记录。" else "登录后继续使用同一账号的问答、历史和健康记录。",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (creating) OutlinedTextField(name, { name = it }, label = { Text("称呼") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(email, { email = it }, label = { Text("邮箱") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(password, { password = it }, label = { Text(if (creating) "密码（至少 10 位，含字母和数字）" else "密码") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), singleLine = true)
        Button(onClick = { onSubmit(creating, name, email, password) }, modifier = Modifier.fillMaxWidth().heightIn(min = 50.dp)) { Text(if (creating) "创建账号" else "登录") }
        OutlinedButton(onClick = onScan, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("扫码绑定网页账号") }
        TextButton(onClick = { creating = !creating }, modifier = Modifier.fillMaxWidth()) { Text(if (creating) "已有账号？返回登录" else "第一次使用？创建账号") }
        if (status.isNotBlank()) StatusMessage(status)
    }
}

@Composable
private fun QuestionPanel(
    api: Api,
    question: String,
    messages: List<ConversationMessage>,
    attachment: Attachment?,
    responseMode: String,
    status: String,
    onModeChange: (String) -> Unit,
    onPickAttachment: () -> Unit,
    onClearAttachment: () -> Unit,
    onQuestionChange: (String) -> Unit,
    onClarification: (String) -> Unit,
    onAsk: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(if (responseMode == "professional") "专业版问答" else "生活版问答", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
        Text(
            if (responseMode == "professional") "围绕临床问题和文献主题组织证据。" else "先给清楚答案，再说明依据和注意事项。",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (responseMode == "life") {
                Button(onClick = { onModeChange("life") }, modifier = Modifier.weight(1f)) { Text("生活版") }
            } else {
                OutlinedButton(onClick = { onModeChange("life") }, modifier = Modifier.weight(1f)) { Text("生活版") }
            }
            if (responseMode == "professional") {
                Button(onClick = { onModeChange("professional") }, modifier = Modifier.weight(1f)) { Text("专业版") }
            } else {
                OutlinedButton(onClick = { onModeChange("professional") }, modifier = Modifier.weight(1f)) { Text("专业版") }
            }
        }
        OutlinedTextField(
            value = question,
            onValueChange = onQuestionChange,
            label = { Text("想问什么？") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 3,
            maxLines = 6,
            shape = RoundedCornerShape(16.dp),
        )
        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onPickAttachment, modifier = Modifier.weight(1f)) { Text("添加图片或文件") }
            attachment?.let { selected ->
                Text(
                    text = selected.name,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                TextButton(onClick = onClearAttachment) { Text("移除") }
            }
        }
        Button(
            onClick = onAsk,
            enabled = question.isNotBlank() || attachment != null,
            modifier = Modifier.fillMaxWidth().heightIn(min = 50.dp),
        ) { Text("发送") }
        if (status.isNotBlank()) StatusMessage(status)
        if (messages.isEmpty()) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
            ) {
                Text("输入问题后，回答会显示在这里。", modifier = Modifier.padding(16.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        } else {
            LazyColumn(
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(bottom = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(messages) { message ->
                    val modules = if (message.role == "assistant" && message.modulePlanRaw != null) api.modulePlan(message.modulePlanRaw) else emptyList()
                    if (modules.isNotEmpty()) {
                        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("EviLife", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
                            ModuleRenderer(modules = modules, api = api, onClarification = onClarification)
                        }
                    } else {
                        Card(
                            Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = if (message.role == "user") Color(0xFFE8F3EF) else Color.White),
                        ) {
                            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(if (message.role == "user") "你" else "EviLife", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
                                Text(message.content)
                                message.fileName?.let { Text("附件：$it", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun HistoryPanel(history: List<Conversation>, status: String, onOpen: (Conversation) -> Unit, onDelete: (Conversation) -> Unit) {
    Column(modifier = Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("最近对话", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
        Text("对话与网页版共用账号数据库。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (history.isEmpty()) {
            StatusMessage(status.ifBlank { "还没有账号对话记录。" })
        } else {
            LazyColumn(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(bottom = 8.dp)) {
                items(history, key = { it.sessionId }) { conversation ->
                    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(conversation.title, maxLines = 2, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Medium)
                            Text(conversation.mode, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            HorizontalDivider()
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                                TextButton(onClick = { onOpen(conversation) }) { Text("打开") }
                                TextButton(onClick = { onDelete(conversation) }) { Text("删除", color = MaterialTheme.colorScheme.error) }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TodayPanel(api: Api, status: String) {
    var today by remember { mutableStateOf<TodayRecords?>(null) }
    var loading by remember { mutableStateOf(true) }
    LaunchedEffect(api) {
        today = runCatching { api.today(LocalDate.now().toString()) }.getOrNull()
        loading = false
    }
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("今日记录", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
        Text("汇总当前账号的客观生活和健康记录。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (loading) Text("正在读取...", color = MaterialTheme.colorScheme.onSurfaceVariant)
        today?.let { record ->
            Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(record.date, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TodayMetric("进食计时", "${record.fasts.size} 条", Modifier.weight(1f))
                        TodayMetric("确认餐食", "${record.mealsCount} 条", Modifier.weight(1f))
                        TodayMetric("健康观察", "${record.observationsCount} 条", Modifier.weight(1f))
                    }
                }
            }
        }
        if (!loading && today == null) StatusMessage(status.ifBlank { "今日记录暂时不可用" })
        FastingPanel(api)
        Spacer(Modifier.padding(bottom = 8.dp))
    }
}

@Composable
private fun TodayMetric(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun FastingPanel(api: Api) {
    val scope = rememberCoroutineScope()
    var active by remember { mutableStateOf<FastRecord?>(null) }
    var working by remember { mutableStateOf(false) }
    var goal by remember { mutableStateOf(16.0) }
    var now by remember { mutableStateOf(System.currentTimeMillis()) }
    var error by remember { mutableStateOf("") }
    LaunchedEffect(api) { active = runCatching { api.activeFast() }.getOrNull() }
    LaunchedEffect(active?.id) {
        while (active != null) {
            now = System.currentTimeMillis()
            delay(1_000)
        }
    }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("进食间隔计时", style = MaterialTheme.typography.titleMedium)
            if (active == null) {
                Text("计时只保存开始和结束时间，不据此生成医疗建议。")
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    listOf(14.0, 16.0, 18.0).forEach { hours ->
                        val selected = goal == hours
                        if (selected) {
                            Button(
                                onClick = { goal = hours },
                                modifier = Modifier.weight(1f).heightIn(min = 44.dp),
                                contentPadding = PaddingValues(horizontal = 4.dp, vertical = 8.dp),
                            ) {
                                Text("${hours.toInt()} 小时", maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                        } else {
                            OutlinedButton(
                                onClick = { goal = hours },
                                modifier = Modifier.weight(1f).heightIn(min = 44.dp),
                                contentPadding = PaddingValues(horizontal = 4.dp, vertical = 8.dp),
                            ) {
                                Text("${hours.toInt()} 小时", maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                        }
                    }
                }
                Button(onClick = {
                    working = true
                    scope.launch {
                        runCatching { api.startFast(goal) }
                            .onSuccess { active = it }
                            .onFailure { error = it.userMessage("启动失败") }
                        working = false
                    }
                }, enabled = !working) { Text(if (working) "启动中..." else "开始记录") }
            } else {
                val start = runCatching { Instant.parse(active!!.startAt).toEpochMilli() }.getOrDefault(now)
                val elapsed = ((now - start).coerceAtLeast(0)) / 1_000
                Text("已记录 ${elapsed / 3_600} 小时 ${(elapsed % 3_600) / 60} 分钟")
                Text("目标：${active!!.goalHours} 小时")
                Button(onClick = {
                    working = true
                    scope.launch {
                        runCatching { api.endFast(active!!.id) }
                            .onSuccess { active = null }
                            .onFailure { error = it.userMessage("结束失败") }
                        working = false
                    }
                }, enabled = !working) { Text(if (working) "保存中..." else "结束并保存") }
            }
            if (error.isNotBlank()) Text(error)
        }
    }
}

@Composable
private fun HealthPanel(
    api: Api,
    reportStatus: String,
    onPickReport: () -> Unit,
    status: String,
    healthAvailable: Boolean,
    onRequestPermissions: () -> Unit,
    onScan: () -> Unit,
) {
    var observations by remember { mutableStateOf<List<HealthObservation>>(emptyList()) }
    var selectedKind by remember { mutableStateOf("weight_kg") }
    var value by remember { mutableStateOf("") }
    var profile by remember { mutableStateOf("") }
    var manualStatus by remember { mutableStateOf("") }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(api) { observations = runCatching { api.listObservations() }.getOrDefault(emptyList()) }
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("健康数据", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
        Text("同步系统健康数据，也可以手动补充日常观察。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Button(onClick = onRequestPermissions, modifier = Modifier.fillMaxWidth().heightIn(min = 50.dp)) { Text("授权并同步") }
        OutlinedButton(onClick = onScan, modifier = Modifier.fillMaxWidth()) { Text("扫码绑定网页账号") }
        if (!healthAvailable) StatusMessage("当前设备未安装或无法使用 Health Connect")

        Text("体检报告", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        OutlinedButton(onClick = onPickReport, modifier = Modifier.fillMaxWidth()) { Text("选择并分析报告") }
        if (reportStatus.isNotBlank()) Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) { Text(reportStatus, Modifier.padding(14.dp)) }

        Text("手动记录", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        listOf(
            "water_ml" to "饮水", "steps" to "步数", "sleep_minutes" to "睡眠", "weight_kg" to "体重",
            "waist_cm" to "腰围", "resting_heart_rate" to "静息心率", "mood_score" to "心情", "note" to "备注",
        ).chunked(2).forEach { row ->
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                row.forEach { (kind, label) ->
                    if (selectedKind == kind) {
                        Button(onClick = { selectedKind = kind }, modifier = Modifier.weight(1f)) { Text(label) }
                    } else {
                        OutlinedButton(onClick = { selectedKind = kind }, modifier = Modifier.weight(1f)) { Text(label) }
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
        OutlinedTextField(value, { value = it }, label = { Text(if (selectedKind == "note") "备注内容" else "${observationLabel(selectedKind)} 数值") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        Button(onClick = {
            val text = value.trim()
            val parsed = if (selectedKind == "note") null else text.toDoubleOrNull()
            if ((selectedKind == "note" && text.isBlank()) || (selectedKind != "note" && (parsed == null || parsed < 0))) {
                manualStatus = "请输入有效的${if (selectedKind == "note") "备注" else "数值"}"
                return@Button
            }
            working = true
            scope.launch {
                runCatching { api.addObservation(selectedKind, parsed, if (selectedKind == "note") text else null) }
                    .onSuccess { observations = listOf(it) + observations; value = ""; manualStatus = "记录已保存" }
                    .onFailure { manualStatus = it.userMessage("保存记录失败") }
                working = false
            }
        }, enabled = !working, modifier = Modifier.fillMaxWidth()) { Text(if (working) "保存中..." else "保存记录") }
        if (manualStatus.isNotBlank()) StatusMessage(manualStatus)
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { scope.launch { observations = runCatching { api.listObservations() }.getOrDefault(observations) } }, modifier = Modifier.weight(1f)) { Text("刷新记录") }
            OutlinedButton(onClick = { scope.launch { profile = runCatching { api.profileSummary() }.getOrDefault("档案分析暂不可用") } }, modifier = Modifier.weight(1f)) { Text("分析健康档案") }
        }
        if (profile.isNotBlank()) Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) { Text(profile, Modifier.padding(14.dp)) }
        if (observations.isNotEmpty()) {
            Text("最近记录", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            observations.take(20).forEach { item ->
                Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                    Text("${item.kind}：${item.value ?: item.note.orEmpty()}\n${item.observedAt} · ${item.source}", Modifier.padding(12.dp))
                }
            }
        }
        if (status.isNotBlank()) StatusMessage(status)
        Spacer(Modifier.padding(bottom = 8.dp))
    }
}

@Composable
private fun SettingsPanel(api: Api, user: User, status: String, onLogout: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("设置", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
        Text("连接地址和当前账号", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(user.displayName, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(user.email, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        OutlinedTextField(value = api.baseUrl, onValueChange = { api.baseUrl = it }, label = { Text("服务器地址") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        Text("健康权限由系统 Health Connect 管理。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Button(onClick = onLogout, modifier = Modifier.fillMaxWidth()) { Text("退出登录") }
        if (status.isNotBlank()) StatusMessage(status)
    }
}

@Composable
private fun StatusMessage(status: String) {
    val isError = listOf("失败", "错误", "无法", "不能", "未获得", "不可用").any { status.contains(it) }
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (isError) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer,
        ),
    ) {
        Text(
            status,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            style = MaterialTheme.typography.bodySmall,
            color = if (isError) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSecondaryContainer,
        )
    }
}

private suspend fun readAttachment(context: android.content.Context, uri: android.net.Uri): Attachment? = withContext(Dispatchers.IO) {
    val contentType = context.contentResolver.getType(uri) ?: "application/octet-stream"
    val name = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
        ?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(cursor.getColumnIndexOrThrow(OpenableColumns.DISPLAY_NAME)) else null
        }
        ?: "attachment"
    val bytes = runCatching { context.contentResolver.openInputStream(uri)?.use { it.readBytes() } }.getOrNull()
        ?: return@withContext null
    val limit = if (contentType.startsWith("image/")) 10 * 1024 * 1024 else 20 * 1024 * 1024
    if (bytes.isNotEmpty() && bytes.size <= limit) Attachment(name, contentType, bytes) else null
}

private fun observationLabel(kind: String): String = when (kind) {
    "water_ml" -> "饮水（ml）"
    "steps" -> "步数"
    "sleep_minutes" -> "睡眠（分钟）"
    "weight_kg" -> "体重（kg）"
    "waist_cm" -> "腰围（cm）"
    "resting_heart_rate" -> "静息心率（次/分）"
    "mood_score" -> "心情（1-5）"
    else -> kind
}

private fun Throwable.userMessage(fallback: String): String = message?.takeIf { it.isNotBlank() } ?: fallback

private fun Throwable.questionErrorMessage(baseUrl: String): String {
    val detail = message?.takeIf { it.isNotBlank() }
    val networkFailure = this is java.net.ConnectException ||
        this is java.net.SocketTimeoutException ||
        this is java.net.UnknownHostException ||
        detail?.contains("failed to connect", ignoreCase = true) == true

    if (!networkFailure) return detail ?: "请求失败"

    return "无法连接问答服务（$baseUrl）。USB 调试时请保持手机连接和电脑后端运行，" +
        "然后执行 adb reverse tcp:8010 tcp:8000；设置中的服务器地址应为 http://127.0.0.1:8010。"
}
