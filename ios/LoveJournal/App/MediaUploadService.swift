/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

import PhotosUI
import SwiftUI
import UIKit

import LoveCore

/// Image compression + upload pipeline shared by articles/albums/timeline/
/// check-ins (Android parity: downscale to ≤1600px longest edge, JPEG q85).
enum MediaUploadService {
    static let albumsPath = "/uploads/albums"
    static let articlesPath = "/uploads/articles"
    static let timelinePath = "/uploads/timeline"
    static let checkinPath = "/uploads/checkin"
    static let videosPath = "/uploads/videos"

    /// Downscales and JPEG-encodes; returns nil for undecodable data.
    static func compressImage(_ data: Data, maxDimension: CGFloat = 1600, quality: CGFloat = 0.85) -> Data? {
        guard let image = UIImage(data: data) else { return nil }
        let longest = max(image.size.width, image.size.height)
        var target = image
        if longest > maxDimension {
            let scale = maxDimension / longest
            let newSize = CGSize(width: image.size.width * scale, height: image.size.height * scale)
            let renderer = UIGraphicsImageRenderer(size: newSize)
            target = renderer.image { _ in
                image.draw(in: CGRect(origin: .zero, size: newSize))
            }
        }
        return target.jpegData(compressionQuality: quality)
    }

    /// Compress then upload to one of the image endpoints; `path` is the
    /// version-relative suffix (e.g. `MediaUploadService.albumsPath`).
    static func uploadImage(_ data: Data, path: String, api: LoveAPIClient) async throws -> WriteDTOs.UploadResult {
        guard let jpeg = compressImage(data) else {
            throw APIError.transport(.other("无法读取图片"))
        }
        return try await api.upload(
            path,
            fileData: jpeg,
            fileName: "upload.jpg",
            mimeType: "image/jpeg"
        )
    }
}

/// SwiftUI PhotosPicker wrapper handing back raw image `Data`.
struct LoveImagePicker: View {
    let onPick: (Data) -> Void
    @State private var item: PhotosPickerItem?

    var body: some View {
        PhotosPicker(selection: $item, matching: .images) {
            Label("common.pick_image", systemImage: "photo.on.rectangle.angled")
        }
        .onChange(of: item) { _, newValue in
            guard let newValue else { return }
            Task {
                if let data = try? await newValue.loadTransferable(type: Data.self) {
                    onPick(data)
                }
                item = nil
            }
        }
    }
}
