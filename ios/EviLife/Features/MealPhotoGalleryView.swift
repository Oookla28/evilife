import SwiftUI
import UIKit

/// 餐食照片图库：网格浏览、点击放大、长按/详情删除。
struct MealPhotoGalleryView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var photos: [URL] = MealPhotoStore.list()
    @State private var selectedPhoto: URL?

    private let columns = [GridItem(.adaptive(minimum: 100), spacing: 4)]

    var body: some View {
        NavigationStack {
            ScrollView {
                if photos.isEmpty {
                    VStack(spacing: 10) {
                        Image(systemName: "photo.on.rectangle.angled")
                            .font(.system(size: 44))
                            .foregroundStyle(EvilifeTheme.textTertiary)
                        Text("还没有餐食照片")
                            .font(.footnote)
                            .foregroundStyle(EvilifeTheme.textTertiary)
                        Text("在「今日 → 餐食 → 拍照记餐」拍的照片会自动存在这里")
                            .font(.caption2)
                            .foregroundStyle(EvilifeTheme.textTertiary)
                    }
                    .padding(.top, 100)
                } else {
                    LazyVGrid(columns: columns, spacing: 4) {
                        ForEach(photos, id: \.self) { url in
                            if let image = UIImage(contentsOfFile: url.path) {
                                Image(uiImage: image)
                                    .resizable()
                                    .scaledToFill()
                                    .frame(minWidth: 0, maxWidth: .infinity)
                                    .aspectRatio(1, contentMode: .fill)
                                    .clipped()
                                    .contentShape(Rectangle())
                                    .onTapGesture { selectedPhoto = url }
                                    .contextMenu {
                                        Button(role: .destructive) {
                                            MealPhotoStore.delete(url)
                                            photos = MealPhotoStore.list()
                                        } label: {
                                            Label("删除", systemImage: "trash")
                                        }
                                    }
                            }
                        }
                    }
                    .padding(4)
                }
            }
            .background(EvilifeTheme.pageBg)
            .navigationTitle("餐食照片")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") { dismiss() }
                }
            }
            .sheet(item: Binding(
                get: { selectedPhoto.map(PhotoURL.init) },
                set: { selectedPhoto = $0?.url }
            )) { wrapper in
                PhotoPreviewView(url: wrapper.url) {
                    photos = MealPhotoStore.list()
                }
            }
        }
    }
}

/// URL 不是 Identifiable，包装一下供 sheet(item:) 使用。
private struct PhotoURL: Identifiable {
    let url: URL
    var id: String { url.lastPathComponent }
}

private struct PhotoPreviewView: View {
    @Environment(\.dismiss) private var dismiss
    let url: URL
    let onChanged: () -> Void

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()
                if let image = UIImage(contentsOfFile: url.path) {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .navigationTitle("照片")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("关闭") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(role: .destructive) {
                        MealPhotoStore.delete(url)
                        onChanged()
                        dismiss()
                    } label: {
                        Image(systemName: "trash")
                    }
                }
            }
        }
    }
}
