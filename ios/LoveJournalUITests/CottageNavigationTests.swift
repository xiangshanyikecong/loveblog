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

import XCTest

/// Navigation regression guard for the cottage section (runs in the local
/// `LoveJournalUI` scheme, not in CI): every pushed screen must show exactly
/// ONE back affordance and one back tap pops exactly ONE level.
///
/// This locks the "double back chevron" fix on the cottage hub → games lobby
/// → board path (the second-level screens were rendering two overlapping back
/// buttons). It replaces the old BackButtonProbeTests diagnostics dump.
///
/// Precondition: the simulator has a logged-in session (this UI scheme is
/// never run against a fresh install); otherwise the test skips.
final class CottageNavigationTests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    /// Back affordances of a navigation bar, identified by POSITION rather than
    /// label: SwiftUI's back button sits in the left third of the bar and its
    /// label is the previous screen's title (not "Back"/"返回"), so label
    /// matching is unreliable. Two overlapping back chevrons — the original
    /// bug — both land here, so "exactly one" is the regression assertion.
    private func leftBackButtons(in app: XCUIApplication) -> [XCUIElement] {
        let bar = app.navigationBars.firstMatch
        let leftEdge = app.frame.width / 3
        return bar.buttons.allElementsBoundByIndex
            .filter { $0.frame.minX < leftEdge }
    }

    private func assertSingleBackButton(_ screen: String, _ app: XCUIApplication) {
        let bar = app.navigationBars.firstMatch
        XCTAssertTrue(bar.waitForExistence(timeout: 8), "no navigation bar on \(screen)")
        let backs = leftBackButtons(in: app)
        XCTAssertEqual(
            backs.count, 1,
            "\(screen) shows \(backs.count) back buttons — double back chevron regressed"
        )
    }

    func testCottageSecondLevelShowsSingleBackButtonAndPopsOneLevel() throws {
        let app = XCUIApplication()
        app.launch()

        let tabBar = app.tabBars.firstMatch
        guard tabBar.waitForExistence(timeout: 15) else {
            throw XCTSkip("No logged-in session on this simulator — log in and re-run")
        }

        // Cottage hub (5th tab).
        tabBar.buttons.element(boundBy: 4).tap()
        let gamesCard = app.buttons.matching(
            NSPredicate(
                format: "label CONTAINS[c] '一起玩' OR label CONTAINS[c] 'play together' OR label CONTAINS[c] '遊ぶ'"
            )
        ).firstMatch
        XCTAssertTrue(gamesCard.waitForExistence(timeout: 8), "games lobby card not found on cottage hub")

        // First level: games lobby — one back button only.
        gamesCard.tap()
        assertSingleBackButton("games lobby", app)

        // Second level: gomoku board — one back button only.
        let gomokuCard = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] '五子棋' OR label CONTAINS[c] 'gomoku'")
        ).firstMatch
        XCTAssertTrue(gomokuCard.waitForExistence(timeout: 8), "gomoku card not found in games lobby")
        gomokuCard.tap()
        assertSingleBackButton("gomoku board", app)

        // One back tap pops exactly ONE level: back to the lobby, not the hub.
        let back = try XCTUnwrap(leftBackButtons(in: app).first, "no back button to tap on gomoku board")
        back.tap()
        XCTAssertTrue(
            gomokuCard.waitForExistence(timeout: 8),
            "after one back tap we should be on the games lobby again, not the cottage hub"
        )
    }
}
