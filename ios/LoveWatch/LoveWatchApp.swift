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

import SwiftUI

/// Companion watch app: love days at a glance plus the two tap actions.
/// All networking rides the phone (see `WatchLink`); the watch never owns
/// a server session.
@main
struct LoveWatchApp: App {
    @State private var link = WatchLink()

    var body: some Scene {
        WindowGroup {
            WatchHomeView()
                .environment(link)
        }
    }
}
