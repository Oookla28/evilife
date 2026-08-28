import Foundation
import HealthKit

final class HealthKitSyncService {
    private let store = HKHealthStore()

    private var readTypes: Set<HKObjectType> {
        let identifiers: [HKQuantityTypeIdentifier] = [
            .stepCount, .bodyMass, .restingHeartRate
        ]
        return Set(identifiers.compactMap { HKObjectType.quantityType(forIdentifier: $0) })
            .union([HKObjectType.categoryType(forIdentifier: .sleepAnalysis)].compactMap { $0 })
    }

    func requestAccess() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw NSError(domain: "EviLife.HealthKit", code: 1)
        }
        try await store.requestAuthorization(toShare: [], read: readTypes)
    }

    /// After authorization, query only the approved types and send aggregate
    /// observations to POST /api/v1/health-connectors/apple_healthkit/ingest.
    /// Authentication must use the signed-in EviLife session; never embed a key.
}
