package com.evilife.android

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.*
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.*

class HealthSync(private val context: Context, private val api: Api) {
    private val client by lazy { HealthConnectClient.getOrCreate(context) }
    val permissions = setOf(HealthPermission.getReadPermission(StepsRecord::class), HealthPermission.getReadPermission(SleepSessionRecord::class), HealthPermission.getReadPermission(HeartRateRecord::class), HealthPermission.getReadPermission(WeightRecord::class))
    suspend fun sync(): String {
        val end = Instant.now(); val start = end.minus(Duration.ofDays(30)); val range = TimeRangeFilter.between(start, end); val out = mutableListOf<Observation>()
        client.readRecords(ReadRecordsRequest(StepsRecord::class, range)).records.groupBy { it.startTime.atZone(ZoneId.systemDefault()).toLocalDate() }.forEach { (d, rows) -> out += Observation("hc:steps:$d", mapOf("kind" to "steps", "value" to rows.sumOf { it.count }.toDouble(), "source" to "device", "observed_at" to d.atStartOfDay(ZoneId.systemDefault()).toInstant().toString(), "connector_id" to "android_health_connect")) }
        client.readRecords(ReadRecordsRequest(WeightRecord::class, range)).records.forEach { out += Observation("hc:weight:${it.time}", mapOf("kind" to "weight_kg", "value" to it.weight.inKilograms, "source" to "device", "observed_at" to it.time.toString(), "connector_id" to "android_health_connect")) }
        return api.ingest(out.take(500))
    }
}
