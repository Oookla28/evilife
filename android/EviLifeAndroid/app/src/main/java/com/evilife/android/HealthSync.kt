package com.evilife.android

import android.content.Context
import androidx.health.connect.client.ExperimentalDeduplicationApi
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.Record
import androidx.health.connect.client.records.RestingHeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.records.WeightRecord
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Duration
import java.time.Instant
import java.time.ZoneId

/** Reads only user-authorized Health Connect data and sends daily aggregates to EviLife. */
class HealthSync(private val context: Context, private val api: Api) {
    private val client by lazy { HealthConnectClient.getOrCreate(context) }

    val permissions: Set<String> = setOf(
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(SleepSessionRecord::class),
        HealthPermission.getReadPermission(RestingHeartRateRecord::class),
        HealthPermission.getReadPermission(WeightRecord::class),
    )

    fun isAvailable(): Boolean = HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE

    suspend fun hasAllPermissions(): Boolean {
        if (!isAvailable()) return false
        return client.permissionController.getGrantedPermissions().containsAll(permissions)
    }

    @OptIn(ExperimentalDeduplicationApi::class)
    suspend fun sync(): String {
        check(isAvailable()) { "当前设备没有可用的 Health Connect" }

        val end = Instant.now()
        val start = end.minus(Duration.ofDays(30))
        val range = TimeRangeFilter.between(start, end)
        val zone = ZoneId.systemDefault()
        val steps = readAll<StepsRecord>(range)
        val sleep = readAll<SleepSessionRecord>(range)
        val heart = readAll<RestingHeartRateRecord>(range)
        val weight = readAll<WeightRecord>(range)

        val stepsByDay = steps.groupBy { it.startTime.atZone(zone).toLocalDate() }
            .mapValues { (_, records) -> records.sumOf { it.count }.toDouble() }
        val sleepByDay = sleep.groupBy { it.startTime.atZone(zone).toLocalDate() }
            .mapValues { (_, records) -> records.sumOf(::sleepMinutes) }
        val heartByDay = heart.groupBy { it.time.atZone(zone).toLocalDate() }
            .mapValues { (_, records) -> records.map { it.beatsPerMinute.toDouble() }.average() }
        val weightByDay = weight.groupBy { it.time.atZone(zone).toLocalDate() }
            .mapValues { (_, records) -> records.maxBy { it.time }.weight.inKilograms }

        val days = buildSet {
            addAll(stepsByDay.keys)
            addAll(sleepByDay.keys)
            addAll(heartByDay.keys)
            addAll(weightByDay.keys)
        }.sorted()
        val observations = buildList {
            days.forEach { day ->
                val observedAt = day.atStartOfDay(zone).toInstant().toString()
                stepsByDay[day]?.let { add(observation("steps", it, day, observedAt)) }
                sleepByDay[day]?.takeIf { it > 0 }?.let { add(observation("sleep_minutes", it, day, observedAt)) }
                heartByDay[day]?.let { add(observation("resting_heart_rate", it, day, observedAt)) }
                weightByDay[day]?.let { add(observation("weight_kg", it, day, observedAt)) }
            }
        }
        check(observations.isNotEmpty()) { "最近 30 天没有可同步的健康数据" }
        return api.ingest(observations.take(Api.MAX_BATCH_SIZE))
    }

    private fun sleepMinutes(record: SleepSessionRecord): Double {
        val stages = record.stages
        if (stages.isEmpty()) return elapsedMinutes(record.startTime, record.endTime)
        val asleepStages = stages.filter {
            it.stage == SleepSessionRecord.STAGE_TYPE_SLEEPING ||
                it.stage == SleepSessionRecord.STAGE_TYPE_LIGHT ||
                it.stage == SleepSessionRecord.STAGE_TYPE_DEEP ||
                it.stage == SleepSessionRecord.STAGE_TYPE_REM
        }
        return asleepStages.sumOf {
            elapsedMinutes(it.startTime, it.endTime)
        }
    }

    private fun elapsedMinutes(start: Instant, end: Instant): Double =
        (end.toEpochMilli() - start.toEpochMilli()) / 60_000.0

    @OptIn(ExperimentalDeduplicationApi::class)
    private suspend inline fun <reified T : Record> readAll(range: TimeRangeFilter): List<T> {
        val records = mutableListOf<T>()
        var pageToken: String? = null
        do {
            val response = client.readRecords(
                ReadRecordsRequest(
                    recordType = T::class,
                    timeRangeFilter = range,
                    pageSize = 1000,
                    pageToken = pageToken,
                ),
            )
            records += response.records
            pageToken = response.pageToken
        } while (!pageToken.isNullOrBlank())
        return records
    }

    private fun observation(kind: String, value: Double, day: java.time.LocalDate, observedAt: String) = Observation(
        external_id = "hc:$kind:$day",
        observation = mapOf(
            "kind" to kind,
            "value" to value,
            "source" to "device",
            "observed_at" to observedAt,
            "connector_id" to "android_health_connect",
        ),
    )
}
