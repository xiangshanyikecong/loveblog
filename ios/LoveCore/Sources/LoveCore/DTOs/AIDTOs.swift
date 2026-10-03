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

/// AI-assist contracts (`/v1/ai/*`), mirroring `server/app/schemas/ai.py`.
/// Feature endpoints answer 503 when the instance has no AI configured;
/// `GET /ai/status` itself always succeeds and drives UI visibility.
public enum AIDTOs {
    /// Feature keys advertised by `/ai/status`.
    public enum Feature {
        public static let articlePolish = "article_polish"
        public static let monthlyReport = "monthly_report"
        public static let questionGenerate = "question_generate"
        public static let semanticSearch = "semantic_search"
    }

    /// `GET /v1/ai/status`.
    public struct Status: Decodable, Equatable {
        public var enabled: Bool
        public var chatModel: String?
        public var embeddingModel: String?
        public var features: [String]

        public func supports(_ feature: String) -> Bool {
            enabled && features.contains(feature)
        }

        enum CodingKeys: String, CodingKey {
            case enabled, features
            case chatModel = "chat_model"
            case embeddingModel = "embedding_model"
        }
    }

    /// `POST /v1/ai/article/polish`. `mode`: polish | continue | proofread.
    public struct PolishRequest: Encodable, Equatable {
        public var content: String
        public var mode: String

        public init(content: String, mode: String) {
            self.content = content
            self.mode = mode
        }
    }

    public struct PolishResponse: Decodable, Equatable {
        public var text: String
    }

    /// `POST /v1/ai/article/search`.
    public struct SemanticSearchRequest: Encodable, Equatable {
        public var query: String
        public var topK: Int

        public init(query: String, topK: Int) {
            self.query = query
            self.topK = topK
        }

        enum CodingKeys: String, CodingKey {
            case query
            case topK = "top_k"
        }
    }

    public struct SemanticSearchResult: Decodable, Identifiable, Equatable {
        public var aid: String
        public var title: String
        public var snippet: String
        /// 0-1 similarity.
        public var score: Double
        public var updatedAt: Date?

        public var id: String { aid }

        enum CodingKeys: String, CodingKey {
            case aid, title, snippet, score
            case updatedAt = "updated_at"
        }
    }

    public struct SemanticSearchResponse: Decodable {
        public var query: String
        public var results: [SemanticSearchResult]
        public var indexedCount: Int

        enum CodingKeys: String, CodingKey {
            case query, results
            case indexedCount = "indexed_count"
        }
    }

    /// `POST /v1/ai/report/monthly`.
    public struct MonthlyReportRequest: Encodable, Equatable {
        public var year: Int
        public var month: Int

        public init(year: Int, month: Int) {
            self.year = year
            self.month = month
        }
    }

    public struct MonthlyReportResponse: Decodable, Equatable {
        public var year: Int
        public var month: Int
        public var text: String
    }

    /// `POST /v1/ai/questions/generate`.
    public struct QuestionsRequest: Encodable, Equatable {
        public var count: Int

        public init(count: Int) {
            self.count = count
        }
    }

    public struct QuestionsResponse: Decodable, Equatable {
        public var questions: [String]
    }
}
