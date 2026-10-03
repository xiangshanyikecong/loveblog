// swift-tools-version: 5.10
/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
//
// LoveCore is the platform-independent protocol layer shared by all Love
// Journal iOS surfaces: address normalization, the REST client, DTOs, the
// E2EE primitives (milestone M3) and the offline outbox (milestone M6).
// It intentionally depends on Foundation only so `swift test` can run on a
// plain macOS/Linux host (the CI gate on Windows-authored code).

import PackageDescription

let package = Package(
    name: "LoveCore",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
        .watchOS(.v10),
    ],
    products: [
        .library(name: "LoveCore", targets: ["LoveCore"]),
    ],
    targets: [
        .target(name: "LoveCore"),
        .testTarget(name: "LoveCoreTests", dependencies: ["LoveCore"]),
    ]
)
