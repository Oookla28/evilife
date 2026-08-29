package com.evilife.android

import android.content.Context
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.UUID

data class Observation(val external_id: String, val observation: Map<String, Any?>)
data class Attachment(val name: String, val contentType: String, val bytes: ByteArray)
data class User(val id: String, val email: String, val displayName: String, val subjectId: String)
data class ModulePlanItem(
    val moduleId: String,
    val type: String,
    val status: String,
    val props: JSONObject,
)
data class ObservationDraft(val kind: String, val value: Double? = null, val note: String? = null)
data class ConversationMessage(
    val id: String,
    val role: String,
    val content: String = "",
    val modulePlanRaw: String? = null,
    val fileName: String? = null,
    val fileType: String? = null,
)
data class Conversation(
    val sessionId: String,
    val title: String,
    val mode: String,
    val updatedAt: String,
    val messages: List<ConversationMessage>,
)
data class FastRecord(
    val id: String,
    val startAt: String,
    val endAt: String?,
    val goalHours: Double,
    val status: String,
)
data class TodayRecords(
    val date: String,
    val fasts: List<FastRecord>,
    val mealsCount: Int,
    val observationsCount: Int,
)
data class HealthObservation(
    val id: String,
    val kind: String,
    val value: Double?,
    val note: String?,
    val source: String,
    val observedAt: String,
)
data class ReportResult(val fileName: String, val summary: String, val limitations: List<String>)

class Api(context: Context) {
    private val prefs = context.getSharedPreferences("evilife", Context.MODE_PRIVATE)
    private val cookieStore = mutableMapOf<String, Cookie>()
    private val cookieKey = "session_cookie"
    private val cookieOriginKey = "session_cookie_origin"
    private val cookieExpiresKey = "session_cookie_expires_at"
    private val client = OkHttpClient.Builder().cookieJar(object : CookieJar {
        override fun saveFromResponse(url: HttpUrl, values: List<Cookie>) {
            synchronized(cookieStore) {
                values.forEach { cookieStore[it.name] = it }
                cookieStore.entries.removeIf { it.value.expiresAt <= System.currentTimeMillis() }
                cookieStore[SESSION_COOKIE_NAME]?.let { cookie ->
                    prefs.edit()
                        .putString(cookieKey, cookie.toString())
                        .putString(cookieOriginKey, origin(url))
                        .putLong(cookieExpiresKey, cookie.expiresAt)
                        .apply()
                } ?: prefs.edit()
                    .remove(cookieKey)
                    .remove(cookieOriginKey)
                    .remove(cookieExpiresKey)
                    .apply()
            }
        }

        override fun loadForRequest(url: HttpUrl): List<Cookie> = synchronized(cookieStore) {
            if (cookieStore.isEmpty()) {
                val serialized = prefs.getString(cookieKey, null)
                val expiresAt = prefs.getLong(cookieExpiresKey, 0L)
                if (serialized != null && expiresAt > System.currentTimeMillis() &&
                    prefs.getString(cookieOriginKey, null) == origin(url)
                ) {
                    Cookie.parse(url, serialized)?.let { cookieStore[it.name] = it }
                } else if (serialized != null) {
                    prefs.edit()
                        .remove(cookieKey)
                        .remove(cookieOriginKey)
                        .remove(cookieExpiresKey)
                        .apply()
                }
            }
            cookieStore.values.filter { it.expiresAt > System.currentTimeMillis() && it.matches(url) }
        }
    }).build()
    var baseUrl: String
        get() = prefs.getString("base_url", DEFAULT_BASE_URL) ?: DEFAULT_BASE_URL
        set(value) = prefs.edit().putString("base_url", value.trim().trimEnd('/')).apply()

    suspend fun claimPairing(rawValue: String): User {
        val payload = PairingParser.parse(rawValue)
            ?: error("无法识别二维码，请扫描 EviLife 网页端配对二维码")
        payload.baseUrl?.let { baseUrl = it }
        return claim(payload.code)
    }

    private suspend fun request(path: String, body: String? = null, method: String? = null): String = withContext(Dispatchers.IO) {
        val b = Request.Builder().url(endpoint(path)).apply {
            when {
                method == "DELETE" -> delete()
                method == "PUT" -> put((body ?: "").toRequestBody("application/json".toMediaType()))
                method == "POST" || body != null -> post((body ?: "").toRequestBody("application/json".toMediaType()))
            }
        }.build()
        client.newCall(b).execute().use { r ->
            if (!r.isSuccessful) error("服务器返回 ${r.code}: ${r.body?.string()}")
            r.body?.string().orEmpty()
        }
    }

    suspend fun login(email: String, password: String): User {
        require(email.isNotBlank()) { "请输入邮箱" }
        require(password.isNotBlank()) { "请输入密码" }
        return parseUser(request(
            "/api/v1/auth/login",
            JSONObject().put("email", email.trim()).put("password", password).toString()))
    }

    suspend fun register(email: String, password: String, displayName: String): User {
        require(email.isNotBlank()) { "请输入邮箱" }
        require(password.isNotBlank()) { "请输入密码" }
        require(displayName.isNotBlank()) { "请输入称呼" }
        return parseUser(request(
            "/api/v1/auth/register",
            JSONObject()
                .put("email", email.trim())
                .put("password", password)
                .put("display_name", displayName.trim())
                .toString()))
    }

    suspend fun currentUser(): User = parseUser(request("/api/v1/auth/me"))

    suspend fun logout() {
        request("/api/v1/auth/logout", method = "POST")
        synchronized(cookieStore) {
            cookieStore.clear()
            prefs.edit().remove(cookieKey).remove(cookieOriginKey).remove(cookieExpiresKey).apply()
        }
    }

    suspend fun orchestrate(
        session: String,
        text: String,
        responseMode: String = "life",
        attachment: Attachment? = null,
    ): String {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM).apply {
            attachment?.let { file ->
                val part = file.bytes.toRequestBody(file.contentType.toMediaType())
                addFormDataPart(if (file.contentType.startsWith("image/")) "image" else "document", file.name, part)
            }
            addFormDataPart("session_id", session)
            addFormDataPart("mode", if (responseMode == "professional") "evaluation" else "auto")
            if (text.isNotBlank()) addFormDataPart("text", text)
        }.build()
        val req = Request.Builder().url(endpoint("/api/v1/orchestrate")).post(body).build()
        return withContext(Dispatchers.IO) {
            client.newCall(req).execute().use { r ->
                if (!r.isSuccessful) error("服务器返回 ${r.code}: ${r.body?.string()}")
                r.body?.string().orEmpty()
            }
        }
    }

    fun modulePlan(raw: String): List<ModulePlanItem> {
        val modules = runCatching { JSONObject(raw).optJSONArray("module_plan") }
            .getOrNull()
            ?: runCatching { JSONArray(raw) }.getOrNull()
            ?: return emptyList()
        return (0 until modules.length()).mapNotNull { index ->
            val item = modules.optJSONObject(index) ?: return@mapNotNull null
            ModulePlanItem(
                moduleId = item.optString("module_id", "module-$index"),
                type = item.optString("type", "unknown"),
                status = item.optString("status", "ready"),
                props = item.optJSONObject("props") ?: JSONObject(),
            )
        }
    }

    fun modulePlanRaw(raw: String): String? =
        runCatching { JSONObject(raw).optJSONArray("module_plan")?.toString() }.getOrNull()

    suspend fun addObservationsBatch(items: List<ObservationDraft>): List<HealthObservation> {
        require(items.isNotEmpty()) { "没有可保存的健康记录" }
        val observations = JSONArray().apply {
            items.forEach { item ->
                put(JSONObject().apply {
                    put("kind", item.kind)
                    put("source", "self_report")
                    item.value?.let { put("value", it) }
                    item.note?.let { put("note", it) }
                })
            }
        }
        val response = JSONArray(request(
            "/api/v1/observations/batch",
            JSONObject().put("observations", observations).toString(),
        ))
        return (0 until response.length()).map { parseObservation(response.getJSONObject(it)) }
    }

    suspend fun confirmAction(actionId: String, payload: JSONObject): JSONObject =
        JSONObject(request("/api/v1/actions/${Uri.encode(actionId)}/confirm", payload.toString()))

    suspend fun claim(code: String): User {
        val normalized = PairingParser.normalizeCode(code)
        require(normalized.length in PairingParser.MIN_CODE_LENGTH..PairingParser.MAX_CODE_LENGTH) {
            "配对码应为 4-16 位字母或数字"
        }
        return parseUser(JSONObject(request(
            "/api/v1/device-pairing/claim",
            JSONObject().put("code", normalized).put("mode", "login").toString())).getJSONObject("user").toString())
    }

    suspend fun listConversations(): List<Conversation> {
        val array = JSONArray(request("/api/v1/conversations?limit=50"))
        return (0 until array.length()).map { parseConversation(array.getJSONObject(it)) }
    }

    suspend fun saveConversation(conversation: Conversation) {
        val messages = JSONArray().apply {
            conversation.messages.forEach { message ->
                put(JSONObject().apply {
                    put("id", message.id)
                    put("role", message.role)
                    put("content", message.content)
                    message.modulePlanRaw?.let { raw -> put("modulePlan", JSONArray(raw)) }
                    message.fileName?.let { name ->
                        put("file", JSONObject().put("name", name).put("type", message.fileType ?: "application/octet-stream"))
                    }
                })
            }
        }
        request(
            "/api/v1/conversations/${Uri.encode(conversation.sessionId)}",
            JSONObject()
                .put("session_id", conversation.sessionId)
                .put("title", conversation.title)
                .put("mode", conversation.mode)
                .put("messages", messages)
                .toString(),
            method = "PUT")
    }

    suspend fun deleteConversation(sessionId: String) {
        request("/api/v1/conversations/${Uri.encode(sessionId)}", method = "DELETE")
    }

    suspend fun activeFast(): FastRecord? {
        val raw = request("/api/v1/fasts/active")
        if (raw.isBlank() || raw == "null") return null
        return parseFast(JSONObject(raw))
    }

    suspend fun fastHistory(): List<FastRecord> {
        val array = JSONArray(request("/api/v1/fasts?limit=20"))
        return (0 until array.length()).map { parseFast(array.getJSONObject(it)) }
    }

    suspend fun startFast(goalHours: Double): FastRecord =
        parseFast(JSONObject(request(
            "/api/v1/fasts/start",
            JSONObject().put("goal_hours", goalHours).toString())))

    suspend fun endFast(id: String): FastRecord =
        parseFast(JSONObject(request("/api/v1/fasts/${Uri.encode(id)}/end", method = "POST")))

    suspend fun today(date: String): TodayRecords {
        val json = JSONObject(request("/api/v1/today?date=${Uri.encode(date)}"))
        val fasts = json.optJSONArray("fasts") ?: JSONArray()
        val meals = json.optJSONArray("meals") ?: JSONArray()
        val observations = json.optJSONArray("observations") ?: JSONArray()
        return TodayRecords(
            date = json.optString("date", date),
            fasts = (0 until fasts.length()).map { parseFast(fasts.getJSONObject(it)) },
            mealsCount = meals.length(),
            observationsCount = observations.length(),
        )
    }

    suspend fun listObservations(): List<HealthObservation> {
        val array = JSONArray(request("/api/v1/observations?limit=100"))
        return (0 until array.length()).map { parseObservation(array.getJSONObject(it)) }
    }

    suspend fun addObservation(kind: String, value: Double?, note: String?): HealthObservation {
        val body = JSONObject().apply {
            put("kind", kind)
            put("source", "self_report")
            if (kind == "note") put("note", note?.trim()) else put("value", value)
        }
        return parseObservation(JSONObject(request("/api/v1/observations", body.toString())))
    }

    suspend fun profileSummary(): String {
        val root = JSONObject(request("/api/v1/profile/analyze", method = "POST"))
        val cards = root.optJSONArray("cards") ?: return "暂无可用健康档案摘要"
        return (0 until cards.length()).mapNotNull { index ->
            val card = cards.optJSONObject(index) ?: return@mapNotNull null
            val title = card.optString("title")
            val preview = card.optString("preview")
            "$title\n$preview".trim()
        }.joinToString("\n\n").ifBlank { "暂无可用健康档案摘要" }
    }

    suspend fun analyzeReport(attachment: Attachment): ReportResult {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", attachment.name, attachment.bytes.toRequestBody(attachment.contentType.toMediaType()))
            .build()
        val reportRequest = Request.Builder().url(endpoint("/api/v1/reports/analyze")).post(body).build()
        val raw = withContext(Dispatchers.IO) {
            client.newCall(reportRequest).execute().use { response ->
                if (!response.isSuccessful) error("服务器返回 ${response.code}: ${response.body?.string()}")
                response.body?.string().orEmpty()
            }
        }
        val json = JSONObject(raw)
        val limitations = json.optJSONArray("limitations") ?: JSONArray()
        return ReportResult(
            fileName = json.optString("file_name", attachment.name),
            summary = json.optString("summary", "报告已上传，未返回摘要。"),
            limitations = (0 until limitations.length()).map { limitations.optString(it) }.filter { it.isNotBlank() },
        )
    }

    fun answerText(raw: String): String {
        val root = runCatching { JSONObject(raw) }.getOrNull() ?: return raw
        val modules = root.optJSONArray("module_plan") ?: return raw
        val parts = mutableListOf<String>()
        for (index in 0 until modules.length()) {
            val props = modules.optJSONObject(index)?.optJSONObject("props") ?: continue
            listOf("conclusion", "explanation", "scope_reason").forEach { key ->
                props.optString(key).takeIf { it.isNotBlank() && it != "null" }?.let { parts += it }
            }
            props.optJSONObject("verdict")?.let { verdict ->
                val label = when (verdict.optString("verdict")) {
                    "true" -> "是"
                    "partly_true" -> "部分正确"
                    "false" -> "否"
                    else -> "证据不足"
                }
                verdict.optString("short_reason").takeIf { it.isNotBlank() }?.let {
                    parts += "裁决：$label。$it"
                }
            }
            props.optJSONArray("general_advice")?.let { advice ->
                val items = (0 until advice.length()).map { advice.optString(it) }.filter { it.isNotBlank() }
                if (items.isNotEmpty()) parts += "建议：${items.joinToString("；")}"
            }
            props.optJSONArray("citations")?.let { citations ->
                val items = (0 until citations.length()).mapNotNull { citationIndex ->
                    val citation = citations.optJSONObject(citationIndex) ?: return@mapNotNull null
                    val title = citation.optString("title").takeIf { it.isNotBlank() } ?: return@mapNotNull null
                    val year = citation.optInt("year").takeIf { it > 0 }?.let { "（$it）" }.orEmpty()
                    "$title$year"
                }
                if (items.isNotEmpty()) parts += "参考证据：${items.joinToString("；")}"
            }
            props.optJSONArray("limitations")?.let { limits ->
                val items = (0 until limits.length()).map { limits.optString(it) }.filter { it.isNotBlank() }
                if (items.isNotEmpty()) parts += "局限：${items.joinToString("；")}"
            }
        }
        return parts.distinct().joinToString("\n\n").ifBlank { raw }
    }

    suspend fun ingest(observations: List<Observation>): String {
        require(observations.isNotEmpty()) { "最近 30 天没有可同步的健康数据" }
        require(observations.size <= MAX_BATCH_SIZE) { "单次健康数据上传不能超过 $MAX_BATCH_SIZE 条" }
        val receipt = "health-connect-${UUID.randomUUID()}"
        val items = observations.joinToString(",") { "{\"external_id\":${json(it.external_id)},\"observation\":${mapJson(it.observation)}}" }
        return request("/api/v1/health-connectors/android_health_connect/ingest", "{\"consent_receipt\":${json(receipt)},\"observations\":[$items]}")
    }

    private fun json(value: String) = JSONObject.quote(value)

    private fun mapJson(values: Map<String, Any?>): String = JSONObject().apply {
        values.forEach { (key, value) -> put(key, value) }
    }.toString()

    private fun normalizeBaseUrl(value: String): String {
        val trimmed = value.trim().trimEnd('/')
        require(trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            "服务器地址必须以 http:// 或 https:// 开头"
        }
        return trimmed
    }

    private fun endpoint(path: String): String = normalizeBaseUrl(baseUrl) + path

    private fun parseUser(raw: String): User {
        val json = JSONObject(raw)
        return User(
            id = json.getString("id"),
            email = json.getString("email"),
            displayName = json.optString("display_name", json.optString("displayName")),
            subjectId = json.optString("subject_id", json.optString("subjectId")),
        )
    }

    private fun parseConversation(json: JSONObject): Conversation {
        val messages = json.optJSONArray("messages") ?: JSONArray()
        return Conversation(
            sessionId = json.getString("session_id"),
            title = json.optString("title", "未命名对话"),
            mode = json.optString("mode", "life"),
            updatedAt = json.optString("updated_at"),
            messages = (0 until messages.length()).map { index ->
                val item = messages.getJSONObject(index)
                ConversationMessage(
                    id = item.optString("id", "message-$index"),
                    role = item.optString("role", "assistant"),
                    content = item.optString("content").takeIf { it.isNotBlank() && it != "null" }
                        ?: modulePlanText(item.optJSONArray("modulePlan")),
                    modulePlanRaw = item.optJSONArray("modulePlan")?.toString(),
                    fileName = item.optJSONObject("file")?.optString("name")?.takeIf { it.isNotBlank() },
                    fileType = item.optJSONObject("file")?.optString("type")?.takeIf { it.isNotBlank() },
                )
            },
        )
    }

    private fun parseFast(json: JSONObject): FastRecord = FastRecord(
        id = json.getString("id"),
        startAt = json.getString("start_at"),
        endAt = json.optString("end_at").takeIf { it.isNotBlank() && it != "null" },
        goalHours = json.optDouble("goal_hours", 16.0),
        status = json.optString("status", "completed"),
    )

    private fun modulePlanText(modules: JSONArray?): String {
        if (modules == null) return ""
        val parts = mutableListOf<String>()
        for (index in 0 until modules.length()) {
            val props = modules.optJSONObject(index)?.optJSONObject("props") ?: continue
            listOf("conclusion", "explanation", "summary").forEach { key ->
                props.optString(key).takeIf { it.isNotBlank() && it != "null" }?.let { parts += it }
            }
        }
        return parts.distinct().joinToString("\n\n")
    }

    private fun parseObservation(json: JSONObject): HealthObservation = HealthObservation(
        id = json.getString("id"),
        kind = json.getString("kind"),
        value = json.optDouble("value").takeUnless { it.isNaN() },
        note = json.optString("note").takeIf { it.isNotBlank() && it != "null" },
        source = json.optString("source", "self_report"),
        observedAt = json.optString("observed_at"),
    )

    private fun origin(url: HttpUrl): String = "${url.scheme}://${url.host}:${url.port}"

    companion object {
        // USB debugging uses adb reverse tcp:8010 -> computer backend tcp:8000.
        private const val DEFAULT_BASE_URL = "http://127.0.0.1:8010"
        private const val SESSION_COOKIE_NAME = "evilife_session"
        const val MAX_BATCH_SIZE = 500
    }
}

data class PairingPayload(val code: String, val baseUrl: String? = null)

object PairingParser {
    const val MIN_CODE_LENGTH = 4
    const val MAX_CODE_LENGTH = 16

    fun parse(rawValue: String): PairingPayload? {
        val raw = rawValue.trim()
        if (raw.isEmpty()) return null

        runCatching { JSONObject(raw) }.getOrNull()?.let { json ->
            val code = json.optString("code").takeIf { it.isNotBlank() }
            if (code != null) {
                return PairingPayload(normalizeCode(code), json.optString("base_url").trim().ifEmpty { null })
            }
        }

        runCatching { Uri.parse(raw) }.getOrNull()?.let { uri ->
            val code = uri.getQueryParameter("code")
            if (!code.isNullOrBlank()) {
                val base = if (!uri.scheme.isNullOrBlank() && !uri.host.isNullOrBlank()) {
                    buildString {
                        append(uri.scheme).append("://").append(uri.host)
                        if (uri.port != -1) append(":").append(uri.port)
                    }
                } else null
                return PairingPayload(normalizeCode(code), base)
            }
            if (!uri.scheme.isNullOrBlank() && !uri.host.isNullOrBlank()) return null
        }

        val normalized = normalizeCode(raw)
        return if (normalized.length in MIN_CODE_LENGTH..MAX_CODE_LENGTH) PairingPayload(normalized) else null
    }

    fun normalizeCode(value: String): String = value.uppercase().filter { it in 'A'..'Z' || it in '0'..'9' }
}
