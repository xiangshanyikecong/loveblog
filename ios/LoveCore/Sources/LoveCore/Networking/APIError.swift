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

/// Unified client-side error with user-presentable Chinese messages,
/// ported from the Android `NetworkErrors.kt` mapping. The server has no
/// error-code envelope — every failure is FastAPI's `{"detail": ...}` — so
/// the HTTP status plus the extracted detail drive the message.
public enum APIError: Error, Equatable {
    /// The configured server address is blank or unusable.
    case serverNotConfigured
    case transport(TransportKind)
    /// Non-2xx response. `detail` is the server-provided FastAPI detail, when readable.
    case http(status: Int, detail: String?)
    case decoding(String)

    public enum TransportKind: Equatable {
        case offline
        case timedOut
        case cannotReachHost
        case insecureConnection
        case other(String)
    }

    /// Whether this HTTP failure means the session is gone and the user must
    /// sign in again (the Android client funnels the same cases into a global
    /// session-expiry event).
    public var isSessionExpired: Bool {
        if case .http(let status, _) = self { return status == 401 }
        return false
    }

    /// Whether this failure is transport-level (offline, timeout, unreachable
    /// host) — exactly the cases where an offline outbox should take over.
    /// The write may still have landed (timeouts are ambiguous), which is why
    /// replays must reuse the original idempotency key.
    public var isTransport: Bool {
        if case .transport = self { return true }
        return false
    }

    public var message: String {
        switch self {
        case .serverNotConfigured:
            return "请先填写服务器地址"
        case .transport(let kind):
            switch kind {
            case .offline:
                return "网络未连接，请检查网络后重试"
            case .timedOut:
                return "连接超时，请检查服务器地址与网络"
            case .cannotReachHost:
                return "无法连接到服务器，请检查地址是否正确（直连后端需带端口 :8000）"
            case .insecureConnection:
                return "安全连接失败，请确认服务器证书有效"
            case .other(let raw):
                return "网络错误：\(raw)"
            }
        case .http(let status, let detail):
            if let detail, !detail.isEmpty { return detail }
            switch status {
            case 401:
                return "未授权，请检查用户名与密码"
            case 403:
                return "访问被拒绝"
            case 404:
                return "服务器可达，但未找到接口（请确认地址含端口 :8000）"
            case 413:
                return "内容过大，请压缩后重试"
            case 429:
                return "操作过于频繁，请稍后再试"
            default:
                return "服务器返回错误 (\(status))"
            }
        case .decoding:
            return "服务器响应格式异常，请确认客户端与服务端版本匹配"
        }
    }

    // MARK: - FastAPI detail extraction

    /// Extracts the `detail` field from a FastAPI error body so the backend
    /// message is surfaced verbatim. Handles both shapes FastAPI emits:
    /// `{"detail": "message"}` and the 422 validation form
    /// `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`.
    public static func serverDetail(from data: Data?) -> String? {
        guard let data, !data.isEmpty else { return nil }
        guard let payload = try? JSONDecoder().decode(DetailEnvelope.self, from: data),
              let detail = payload.detail
        else { return nil }
        switch detail {
        case .text(let message):
            return message.isEmpty ? nil : message
        case .validation(let items):
            let joined = items.compactMap(\.friendlyMessage).joined(separator: "；")
            return joined.isEmpty ? nil : joined
        }
    }

    private struct DetailEnvelope: Decodable {
        let detail: DetailValue?
    }

    private enum DetailValue: Decodable {
        case text(String)
        case validation([ValidationItem])

        init(from decoder: Decoder) throws {
            let container = try decoder.singleValueContainer()
            if let text = try? container.decode(String.self) {
                self = .text(text)
                return
            }
            if let items = try? container.decode([ValidationItem].self) {
                self = .validation(items)
                return
            }
            throw DecodingError.typeMismatch(
                DetailValue.self,
                .init(codingPath: decoder.codingPath, debugDescription: "Unsupported detail shape")
            )
        }
    }

    private struct ValidationItem: Decodable {
        let msg: String?
        let loc: [LocEntry]?

        struct LocEntry: Decodable {
            let description: String

            init(from decoder: Decoder) throws {
                let container = try decoder.singleValueContainer()
                if let text = try? container.decode(String.self) {
                    description = text
                } else if let number = try? container.decode(Int.self) {
                    description = String(number)
                } else {
                    description = ""
                }
            }
        }

        var friendlyMessage: String? {
            guard let msg, !msg.isEmpty else { return nil }
            let path = (loc ?? []).map(\.description).filter { !$0.isEmpty }
            if path.isEmpty { return msg }
            return "\(path.joined(separator: ".")): \(msg)"
        }
    }

    // MARK: - Transport classification

    public static func transport(from error: Error) -> APIError {
        let urlError = error as? URLError
        switch urlError?.code {
        case .notConnectedToInternet, .networkConnectionLost, .dataNotAllowed, .internationalRoamingOff:
            return .transport(.offline)
        case .timedOut:
            return .transport(.timedOut)
        case .cannotFindHost, .cannotConnectToHost, .cannotParseResponse, .dnsLookupFailed:
            return .transport(.cannotReachHost)
        case .secureConnectionFailed, .serverCertificateUntrusted, .clientCertificateRejected,
             .serverCertificateHasBadDate, .serverCertificateHasUnknownRoot:
            return .transport(.insecureConnection)
        default:
            return .transport(.other(urlError.map { $0.localizedDescription } ?? error.localizedDescription))
        }
    }
}
