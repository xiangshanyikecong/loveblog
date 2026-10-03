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

import Foundation

/// Couple achievements contracts (`/v1/cottage/achievements`), mirroring
/// `server/app/schemas/achievements.py`.
public enum AchievementDTOs {
    public struct CoupleLevel: Decodable, Equatable {
        public var level: Int
        public var title: String
        public var points: Int
        /// Points required for the next level; nil at the max level.
        public var nextLevelPoints: Int?
        public var nextLevelTitle: String?
        /// 0-100 progress towards the next level (100 at max level).
        public var progressPercent: Int

        enum CodingKeys: String, CodingKey {
            case level, title, points
            case nextLevelPoints = "next_level_points"
            case nextLevelTitle = "next_level_title"
            case progressPercent = "progress_percent"
        }
    }

    public struct BadgeProgress: Decodable, Identifiable, Equatable {
        public var code: String
        public var name: String
        public var description: String
        public var icon: String
        /// record | habit | interact | time
        public var category: String
        /// none | bronze | silver | gold (highest achieved tier)
        public var tier: String
        public var achieved: Bool
        public var current: Int
        public var nextTarget: Int?

        public var id: String { code }

        enum CodingKeys: String, CodingKey {
            case code, name, description, icon, category, tier, achieved, current
            case nextTarget = "next_target"
        }
    }

    public struct Achievements: Decodable {
        public var generatedAt: Date
        /// Aggregated couple counters; keys are stable server stat names
        /// (`love_days`, `articles`, `checkin_streak_days`, …).
        public var stats: [String: Int]
        public var level: CoupleLevel
        public var badges: [BadgeProgress]

        enum CodingKeys: String, CodingKey {
            case stats, level, badges
            case generatedAt = "generated_at"
        }
    }
}
