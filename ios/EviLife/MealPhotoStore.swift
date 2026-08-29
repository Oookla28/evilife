import Foundation

/// 餐食照片本地图库：拍照/选图后自动保存到 Documents/MealPhotos。
enum MealPhotoStore {
    static var directory: URL {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("MealPhotos", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    static func save(_ data: Data) {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        let name = "\(formatter.string(from: Date()))-\(UUID().uuidString.prefix(4)).jpg"
        let url = directory.appendingPathComponent(name)
        try? data.write(to: url, options: .atomic)
    }

    /// 按文件名（时间戳前缀）倒序返回所有照片
    static func list() -> [URL] {
        let urls = (try? FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles])) ?? []
        return urls
            .filter { $0.pathExtension.lowercased() == "jpg" }
            .sorted { $0.lastPathComponent > $1.lastPathComponent }
    }

    static func delete(_ url: URL) {
        try? FileManager.default.removeItem(at: url)
    }
}
