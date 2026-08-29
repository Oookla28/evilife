package com.evilife.android

import android.content.Context
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.*
import java.time.Instant
import java.util.UUID

data class Observation(val external_id: String, val observation: Map<String, Any?>)

class Api(context: Context) {
    private val prefs = context.getSharedPreferences("evilife", Context.MODE_PRIVATE)
    private val client = OkHttpClient.Builder().cookieJar(object : CookieJar {
        private var cookies = mutableListOf<Cookie>()
        override fun saveFromResponse(url: HttpUrl, values: List<Cookie>) { cookies = values.toMutableList() }
        override fun loadForRequest(url: HttpUrl) = cookies
    }).build()
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
    var baseUrl: String get() = prefs.getString("base_url", "http://192.168.43.5:8000")!!; set(v) = prefs.edit().putString("base_url", v.trimEnd('/')).apply()
    private fun request(path: String, body: String? = null): String {
        val b = Request.Builder().url(baseUrl + path).apply { if (body != null) post(body.toRequestBody("application/json".toMediaType())) }.build()
        client.newCall(b).execute().use { r -> if (!r.isSuccessful) error("服务器返回 ${r.code}: ${r.body?.string()}"); return r.body?.string().orEmpty() }
    }
    fun login(email: String, password: String) = request("/api/v1/auth/login", "{\"email\":${json(email)},\"password\":${json(password)}}")
    fun orchestrate(session: String, text: String): String {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("session_id", session).addFormDataPart("mode", "auto").addFormDataPart("text", text).build()
        val req = Request.Builder().url(baseUrl + "/api/v1/orchestrate").post(body).build()
        client.newCall(req).execute().use { r -> if (!r.isSuccessful) error("服务器返回 ${r.code}: ${r.body?.string()}"); return r.body?.string().orEmpty() }
    }
    fun claim(code: String) = request("/api/v1/device-pairing/claim", "{\"code\":${json(code)},\"mode\":\"login\"}")
    fun ingest(observations: List<Observation>): String {
        val receipt = "health-connect-${UUID.randomUUID()}"
        val items = observations.joinToString(",") { "{\"external_id\":${json(it.external_id)},\"observation\":${mapJson(it.observation)}}" }
        return request("/api/v1/health-connectors/android_health_connect/ingest", "{\"consent_receipt\":${json(receipt)},\"observations\":[$items]}")
    }
    private fun json(v: String) = "\"" + v.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
    private fun mapJson(m: Map<String, Any?>) = m.entries.joinToString(prefix="{", postfix="}") { (k,v) -> "\"$k\":" + when(v) { null -> "null"; is Number -> v.toString(); else -> json(v.toString()) } }
}
