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

import Foundation

/// 单次重放失败后的处置决定（与 Android 的 `SyncFailure` 对齐）。
public enum OutboxFailure: Equatable, Sendable {
    /// 暂时性失败（网络 / 5xx / 限流），按退避节奏稍后重试。
    case retryable(String)

    /// 请求本身不可能再成功（4xx / 载荷与服务端模型漂移），转入死信，不再重放。
    case permanent(String)
}

/// 离线队列的失败分类与指数退避策略，镜像 Android 的 `SyncRetryPolicy`：
/// - 永久失败（4xx 等）立即死信，只保留诊断信息；
/// - 暂时失败按 1 分钟起步、2 倍指数增长、上限 6 小时、±20% 抖动的节奏重试；
/// - 连续重试超过 `maxAttempts` 次的暂时失败也转入死信，防止长期占用队列。
public enum OutboxRetryPolicy {
    /// 暂时失败的最大尝试次数（含首次），超过后转入死信。
    public static let maxAttempts = 8

    static let baseDelay: TimeInterval = 60
    static let maxDelay: TimeInterval = 6 * 60 * 60
    static let jitterRatio: Double = 0.2

    public static func classify(_ error: Error) -> OutboxFailure {
        switch error {
        case let apiError as APIError:
            switch apiError {
            case .transport, .serverNotConfigured:
                // 断网、DNS、超时（以及服务器地址未配置）大概率能自愈。
                return .retryable(apiError.message)
            case .http(let status, _):
                switch status {
                case 408, 429, 500...599:
                    // 请求超时 / 限流 / 服务端错误都值得稍后重试。
                    return .retryable(apiError.message)
                case 400...499:
                    // 请求本身不可能再成功，重试只会得到同样的 4xx。
                    return .permanent(apiError.message)
                default:
                    return .retryable(apiError.message)
                }
            case .decoding:
                // 载荷无法被服务端模型解析：重试只会得到同样的 422。
                return .permanent(apiError.message)
            }
        default:
            // 未知异常按客户端 bug 处理，重试无意义（Android 同策略）。
            return .permanent(String(describing: error))
        }
    }

    /// 第 `attemptsSoFar` 次失败后的下次可重试延迟（秒）：
    /// 约 1 分钟起步，每次翻倍，封顶约 6 小时，附 ±20% 抖动，下限 30 秒。
    public static func backoffSeconds(attemptsSoFar: Int) -> TimeInterval {
        let shift = max(0, min(16, attemptsSoFar - 1))
        let exponential = min(baseDelay * pow(2, Double(shift)), maxDelay)
        let jitter = exponential * jitterRatio * Double.random(in: -1...1)
        return max(exponential + jitter, baseDelay / 2)
    }
}
