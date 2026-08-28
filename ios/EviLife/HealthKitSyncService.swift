import Foundation
import HealthKit

/// EviLife iPhone 健康同步桥。
///
/// 网页不能凭 Apple 账户直接读取「健康」数据。正确流程：
/// 1. 用户在 iPhone 上使用 Apple 账户继续；
/// 2. 系统显示 HealthKit 逐类授权页；
/// 3. 本服务只读取获准类型的聚合值（步数、睡眠、静息心率、体重）；
/// 4. 使用 EviLife 登录会话把聚合记录 POST 到
///    /api/v1/health-connectors/apple_healthkit/ingest。
///
/// 用户拒绝某一类权限时，不得推断或绕过：查询前逐类核对授权状态。
@MainActor
final class HealthKitSyncService: ObservableObject {
    private let store = HKHealthStore()

    @Published var isAuthorized = false
    @Published var lastSyncAt: Date?
    @Published var lastAccepted = 0
    @Published var lastSkipped = 0
    @Published var syncing = false
    @Published var lastError: String?

    struct DayAggregates: Identifiable {
        let day: String // yyyy-MM-dd
        var steps: Double?
        var sleepMinutes: Double?
        var restingHeartRate: Double?
        var weightKg: Double?
        var id: String { day }

        var hasData: Bool { steps != nil || sleepMinutes != nil || restingHeartRate != nil || weightKg != nil }
        var count: Int {
            [steps, sleepMinutes, restingHeartRate, weightKg].compactMap { $0 }.count
        }
    }

    private var readTypes: Set<HKObjectType> {
        let identifiers: [HKQuantityTypeIdentifier] = [.stepCount, .bodyMass, .restingHeartRate]
        return Set(identifiers.compactMap { HKObjectType.quantityType(forIdentifier: $0) })
            .union([HKObjectType.categoryType(forIdentifier: .sleepAnalysis)].compactMap { $0 })
    }

    func isHealthDataAvailable() -> Bool {
        HKHealthStore.isHealthDataAvailable()
    }

    func requestAccess() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw NSError(domain: "EviLife.HealthKit", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "当前设备没有可用的健康数据。"])
        }
        try await store.requestAuthorization(toShare: [], read: readTypes)
        isAuthorized = true
    }

    /// 逐类核对授权状态，只查询用户允许的类型。
    private func authorizedTypes() async -> Set<HKObjectType> {
        var result: Set<HKObjectType> = []
        for type in readTypes {
            let status = store.authorizationStatus(for: type)
            if status == .sharingAuthorized { result.insert(type) }
        }
        return result
    }

    // MARK: Queries (last `days` days, day-binned)

    func query(days: Int = 30) async throws -> [DayAggregates] {
        guard isHealthDataAvailable() else {
            throw NSError(domain: "EviLife.HealthKit", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "当前设备没有可用的健康数据。"])
        }
        let allowed = await authorizedTypes()
        guard !allowed.isEmpty else {
            throw NSError(domain: "EviLife.HealthKit", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "没有任何已授权的健康数据类型。"])
        }

        var stepsByDay: [String: Double] = [:]
        var heartByDay: [String: Double] = [:]
        var sleepByDay: [String: Double] = [:]
        var weightByDay: [String: Double] = [:]

        if let type = HKObjectType.quantityType(forIdentifier: .stepCount), allowed.contains(type) {
            stepsByDay = try await dailyStatistics(type, options: .cumulativeSum, days: days)
        }
        if let type = HKObjectType.quantityType(forIdentifier: .restingHeartRate), allowed.contains(type) {
            heartByDay = try await dailyStatistics(type, options: .discreteAverage, days: days)
        }
        if let type = HKObjectType.categoryType(forIdentifier: .sleepAnalysis), allowed.contains(type) {
            sleepByDay = try await dailySleepMinutes(days: days)
        }
        if let type = HKObjectType.quantityType(forIdentifier: .bodyMass), allowed.contains(type) {
            weightByDay = try await dailyLatestSample(type, unit: HKUnit.gramUnit(with: .kilo), days: days)
        }

        var daysSet = Set(stepsByDay.keys)
        daysSet.formUnion(heartByDay.keys)
        daysSet.formUnion(sleepByDay.keys)
        daysSet.formUnion(weightByDay.keys)

        return daysSet.sorted().map { day in
            DayAggregates(
                day: day,
                steps: stepsByDay[day],
                sleepMinutes: sleepByDay[day],
                restingHeartRate: heartByDay[day],
                weightKg: weightByDay[day])
        }
    }

    // MARK: Sync to EviLife backend

    /// 生成聚合记录（供同步 / 跨账号传输复用）。
    func buildObservations(days: Int = 30) async throws -> [ConnectorObservation] {
        let aggregates = try await query(days: days)
        var observations: [ConnectorObservation] = []
        for day in aggregates where day.hasData {
            let observedAt = "\(day.day)T12:00:00+00:00"
            if let value = day.steps {
                observations.append(item(kind: "steps", value: value.rounded(), day: day.day, observedAt: observedAt))
            }
            if let value = day.sleepMinutes {
                observations.append(item(kind: "sleep_minutes", value: value.rounded(), day: day.day, observedAt: observedAt))
            }
            if let value = day.restingHeartRate {
                observations.append(item(kind: "resting_heart_rate", value: (value * 10).rounded() / 10, day: day.day, observedAt: observedAt))
            }
            if let value = day.weightKg {
                observations.append(item(kind: "weight_kg", value: (value * 100).rounded() / 100, day: day.day, observedAt: observedAt))
            }
        }
        guard !observations.isEmpty else {
            throw NSError(domain: "EviLife.HealthKit", code: 3,
                          userInfo: [NSLocalizedDescriptionKey: "最近 \(days) 天没有可同步的健康数据。"])
        }
        return Array(observations.prefix(500))
    }

    /// 把已生成的聚合记录写入自己的账号。
    func ingest(observations: [ConnectorObservation]) async throws -> ConnectorIngestResponse {
        let consentReceipt = "healthkit-consent-\(UUID().uuidString)"
        let response = try await API.ingest(
            connectorId: "apple_healthkit",
            consentReceipt: consentReceipt,
            observations: observations)
        lastSyncAt = Date()
        lastAccepted = response.accepted
        lastSkipped = response.skipped
        lastError = nil
        return response
    }

    /// After authorization, query only the approved types and send aggregate
    /// observations to POST /api/v1/health-connectors/apple_healthkit/ingest.
    /// Authentication uses the signed-in EviLife session; never embed a key.
    func sync(days: Int = 30) async throws -> ConnectorIngestResponse {
        syncing = true
        defer { syncing = false }
        return try await ingest(observations: buildObservations(days: days))
    }

    private func item(kind: String, value: Double, day: String, observedAt: String) -> ConnectorObservation {
        ConnectorObservation(
            external_id: "hk:\(kind):\(day)",
            observation: ObservationCreate(
                kind: kind, value: value, source: "device",
                observedAt: observedAt))
    }

    // MARK: HK query helpers

    private func dailyStatistics(
        _ type: HKQuantityType,
        options: HKStatisticsOptions,
        days: Int
    ) async throws -> [String: Double] {
        let calendar = Calendar.current
        let end = Date()
        guard let start = calendar.date(byAdding: .day, value: -days, to: end) else { return [:] }
        let anchor = calendar.startOfDay(for: start)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKStatisticsCollectionQuery(
                quantityType: type,
                quantitySamplePredicate: nil,
                options: options,
                anchorDate: anchor,
                intervalComponents: DateComponents(day: 1))
            var results: [String: Double] = [:]
            query.initialResultsHandler = { _, collection, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                guard let collection else {
                    continuation.resume(returning: results)
                    return
                }
                let formatter = DateFormatter()
                formatter.dateFormat = "yyyy-MM-dd"
                let isSteps = type.identifier == HKQuantityTypeIdentifier.stepCount.rawValue
                let unit: HKUnit = isSteps ? .count() : HKUnit.count().unitDivided(by: .minute())
                collection.enumerateStatistics(from: start, to: end) { statistics, _ in
                    let quantity: HKQuantity? = options == .cumulativeSum
                        ? statistics.sumQuantity()
                        : statistics.averageQuantity()
                    guard let quantity else { return }
                    results[formatter.string(from: statistics.startDate)] = quantity.doubleValue(for: unit)
                }
                continuation.resume(returning: results)
            }
            store.execute(query)
        }
    }

    private func dailySleepMinutes(days: Int) async throws -> [String: Double] {
        guard let type = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else { return [:] }
        let calendar = Calendar.current
        let end = Date()
        guard let start = calendar.date(byAdding: .day, value: -days, to: end) else { return [:] }
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: [])
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: type, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: [sort]) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                var minutes: [String: Double] = [:]
                let formatter = DateFormatter()
                formatter.dateFormat = "yyyy-MM-dd"
                for sample in (samples as? [HKCategorySample] ?? []) {
                    let value = sample.value
                    let asleepValues: Set<Int> = [
                        HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue,
                        HKCategoryValueSleepAnalysis.asleepCore.rawValue,
                        HKCategoryValueSleepAnalysis.asleepDeep.rawValue,
                        HKCategoryValueSleepAnalysis.asleepREM.rawValue,
                    ]
                    guard asleepValues.contains(value) else { continue }
                    let mins = sample.endDate.timeIntervalSince(sample.startDate) / 60
                    let day = formatter.string(from: sample.startDate)
                    minutes[day, default: 0] += mins
                }
                continuation.resume(returning: minutes)
            }
            store.execute(query)
        }
    }

    private func dailyLatestSample(
        _ type: HKQuantityType,
        unit: HKUnit,
        days: Int
    ) async throws -> [String: Double] {
        let calendar = Calendar.current
        let end = Date()
        guard let start = calendar.date(byAdding: .day, value: -days, to: end) else { return [:] }
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: [])
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: type, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: [sort]) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                var latest: [String: (Date, Double)] = [:]
                let formatter = DateFormatter()
                formatter.dateFormat = "yyyy-MM-dd"
                for sample in (samples as? [HKQuantitySample] ?? []) {
                    let day = formatter.string(from: sample.startDate)
                    let value = sample.quantity.doubleValue(for: unit)
                    if let current = latest[day], sample.startDate < current.0 { continue }
                    latest[day] = (sample.startDate, value)
                }
                continuation.resume(returning: latest.mapValues { $0.1 })
            }
            store.execute(query)
        }
    }
}
