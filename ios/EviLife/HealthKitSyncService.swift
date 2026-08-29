import Foundation
import HealthKit
import UIKit

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
    private var store = HKHealthStore()

    /// code 6（数据库保护态）时重建连接重试
    private func resetStore() {
        store = HKHealthStore()
    }

    @Published var isAuthorized = false
    /// 是否已向系统请求过授权（iOS 26+ 读取授权状态受隐私保护，无法逐类查询，
    /// 只能通过 getRequestStatusForAuthorization 得知是否已请求）。
    @Published var accessRequested = false
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

    /// 供 iOS 26+ 的 .healthDataAccessRequest 修饰符使用。
    var storeInstance: HKHealthStore { store }

    /// 刷新授权状态：系统只在「是否已请求过」层面给出可靠信息。
    func refreshAccessState() async {
        let status = await requestStatus()
        accessRequested = (status == .unnecessary)
        isAuthorized = accessRequested
    }

    func requestAccess() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw NSError(domain: "EviLife.HealthKit", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "当前设备没有可用的健康数据。"])
        }
        try await store.requestAuthorization(toShare: [], read: readTypes)
        await refreshAccessState()
    }

    private func requestStatus() async -> HKAuthorizationRequestStatus {
        await withCheckedContinuation { continuation in
            store.getRequestStatusForAuthorization(toShare: [], read: readTypes) { status, _ in
                continuation.resume(returning: status)
            }
        }
    }

    private var readTypesByKind: [(String, HKObjectType)] {
        [
            ("steps", HKObjectType.quantityType(forIdentifier: .stepCount)!),
            ("resting_heart_rate", HKObjectType.quantityType(forIdentifier: .restingHeartRate)!),
            ("weight_kg", HKObjectType.quantityType(forIdentifier: .bodyMass)!),
            ("sleep_minutes", HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!),
        ]
    }

    /// 供 iOS 26+ 的 .healthDataAccessRequest 修饰符使用。
    var healthReadTypes: Set<HKObjectType> { readTypes }

    // MARK: Queries (last `days` days, day-binned)

    func query(days: Int = 30) async throws -> [DayAggregates] {
        guard isHealthDataAvailable() else {
            throw NSError(domain: "EviLife.HealthKit", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "当前设备没有可用的健康数据。"])
        }
        // HealthKit 数据受系统文件保护：设备锁屏时查询会报
        // 「Protected health data is inaccessible」。解锁后才能读。
        guard UIApplication.shared.isProtectedDataAvailable else {
            throw NSError(domain: "EviLife.HealthKit", code: 6,
                          userInfo: [NSLocalizedDescriptionKey:
                            "设备已锁定，健康数据受系统保护。请解锁手机后回到 App（会自动重试同步）。"])
        }

        // code 6 = HKErrorDatabaseInaccessible：iOS 26/27 上健康数据库可能短暂/持续
        // 处于保护态（系统级问题）。自动重试几次；仍失败则提示重启设备。
        var lastError: Error?
        for attempt in 0..<3 {
            do {
                return try await runHealthQueries(days: days)
            } catch {
                lastError = error
                let ns = error as NSError
                if ns.domain == "com.apple.healthkit", ns.code == 6 {
                    print("[HK] database inaccessible，重建连接后第 \(attempt + 1) 次重试…")
                    resetStore()
                    try? await Task.sleep(nanoseconds: UInt64(1_200_000_000 * (attempt + 1)))
                    continue
                }
                throw error
            }
        }
        throw lastError ?? NSError(domain: "EviLife.HealthKit", code: 6,
            userInfo: [NSLocalizedDescriptionKey: "健康数据库暂不可访问。"])
    }

    private func runHealthQueries(days: Int) async throws -> [DayAggregates] {
        // GPT/Claude 式做法：授权页给用户后，不做任何状态门槛，直接查询。
        // 已授权 → 返回数据；未授权/无数据 → 返回空，由上层提示。
        var stepsByDay: [String: Double] = [:]
        var heartByDay: [String: Double] = [:]
        var sleepByDay: [String: Double] = [:]
        var weightByDay: [String: Double] = [:]

        if let type = HKObjectType.quantityType(forIdentifier: .stepCount) {
            stepsByDay = try await dailyStatistics(type, options: .cumulativeSum, days: days)
        }
        if let type = HKObjectType.quantityType(forIdentifier: .restingHeartRate) {
            heartByDay = try await dailyStatistics(type, options: .discreteAverage, days: days)
        }
        if let type = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) {
            sleepByDay = try await dailySleepMinutes(days: days)
        }
        if let type = HKObjectType.quantityType(forIdentifier: .bodyMass) {
            weightByDay = try await dailyLatestSample(type, unit: HKUnit.gramUnit(with: .kilo), days: days)
        }

        print("[HK] query days=\(days): steps=\(stepsByDay.count) sleep=\(sleepByDay.count) heart=\(heartByDay.count) weight=\(weightByDay.count)")

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
                          userInfo: [NSLocalizedDescriptionKey:
                            "最近 \(days) 天没有可同步的健康数据。若已授权但查询为空，可能是读取被拒绝：请到 设置 → 健康 → 数据访问与设备 → EviLife 中检查，并确认 iPhone 健康里有手表同步的数据。"])
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

#if targetEnvironment(simulator)
// 模拟器验证辅助：以 -seed-sim-health 启动时，授权后自动写入 7 天样例数据，
// 用于验证「授权 → 查询 → 上传」全链路（真机不使用）。
extension HealthKitSyncService {
    static func seedSimulatorHealthDataIfRequested() async {
        guard ProcessInfo.processInfo.arguments.contains("-seed-sim-health") else { return }
        let store = HKHealthStore()
        let stepType = HKObjectType.quantityType(forIdentifier: .stepCount)!
        let heartType = HKObjectType.quantityType(forIdentifier: .restingHeartRate)!
        let weightType = HKObjectType.quantityType(forIdentifier: .bodyMass)!
        let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!
        let readTypes: Set<HKObjectType> = [stepType, heartType, weightType, sleepType]
        let shareTypes: Set<HKSampleType> = [stepType, heartType, weightType]

        do {
            try await store.requestAuthorization(toShare: shareTypes, read: readTypes)
        } catch {
            print("[SEED] 授权请求失败: \(error)")
            return
        }
        guard store.authorizationStatus(for: stepType) == .sharingAuthorized else {
            print("[SEED] 未获得写入授权（用户可能点了拒绝）")
            return
        }

        let calendar = Calendar.current
        let today = Date()
        for offset in 0..<7 {
            guard let day = calendar.date(byAdding: .day, value: -offset, to: today),
                  let noon = calendar.date(bySettingHour: 12, minute: 0, second: 0, of: day),
                  let morning = calendar.date(bySettingHour: 8, minute: 0, second: 0, of: day),
                  let night = calendar.date(bySettingHour: 23, minute: 30, second: 0, of: day)
            else { continue }

            let steps = HKQuantitySample(
                type: stepType,
                quantity: HKQuantity(unit: .count(), doubleValue: Double(6000 + offset * 300)),
                start: noon, end: noon.addingTimeInterval(60))
            let heart = HKQuantitySample(
                type: heartType,
                quantity: HKQuantity(unit: HKUnit.count().unitDivided(by: .minute()), doubleValue: Double(58 + offset % 5)),
                start: morning, end: morning)
            let weight = HKQuantitySample(
                type: weightType,
                quantity: HKQuantity(unit: HKUnit.gramUnit(with: .kilo), doubleValue: 65.2 + Double(offset) * 0.05),
                start: morning, end: morning)
            let sleep = HKCategorySample(
                type: sleepType,
                value: HKCategoryValueSleepAnalysis.asleepCore.rawValue,
                start: night.addingTimeInterval(-7 * 3600), end: night)
            try? await store.save([steps, heart, weight, sleep])
        }
        print("[SEED] 已写入 7 天样例数据（步数/心率/体重/睡眠）")

        // 全链路验证：复用生产代码路径 查询 → 聚合 → 上传
        do {
            let service = HealthKitSyncService()
            let observations = try await service.buildObservations(days: 7)
            print("[SEED] 聚合出 \(observations.count) 条观测")
            let response = try await service.ingest(observations: observations)
            print("[SEED] 上传成功 accepted=\(response.accepted) skipped=\(response.skipped)")
        } catch {
            print("[SEED] 验证失败: \(error)")
        }
    }
}
#endif
