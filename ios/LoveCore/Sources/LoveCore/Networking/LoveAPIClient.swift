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

/// The REST client for the Love Journal backend.
///
/// Session handling mirrors the Android client: the real JWT only ever lives
/// in the `access_token` HttpOnly cookie, carried automatically by
/// `HTTPCookieStorage`. Any 401 outside `/auth/login` / `/auth/logout` fires
/// `onSessionExpired` once — the app then clears local state and returns to
/// the login screen. There is deliberately **no** token refresh: sessions are
/// revoked server-side via `session_version` and simply expire.
public final class LoveAPIClient {
    /// Called on the main thread when a request proves the session is gone.
    public var onSessionExpired: (() -> Void)?

    private let baseURLProvider: () -> String
    private let session: URLSession
    private let publicSession: URLSession

    /// Paths whose 401 responses are part of the normal flow, not a session
    /// expiry signal (mirrors Android's `AuthStatusInterceptor` exemptions).
    private static let exemptPaths: [String] = ["/auth/login", "/auth/logout"]

    public init(baseURLProvider: @escaping () -> String) {
        self.baseURLProvider = baseURLProvider

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 600
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        // The server only records the User-Agent (device list readability);
        // it never validates it.
        config.httpAdditionalHeaders = ["User-Agent": "LoveJournal-iOS/0.1.0"]
        session = URLSession(configuration: config)

        // Cookieless client for health checks against *candidate* servers:
        // never leak the current session's cookie to a host the user is only
        // probing (ported from Android AuthRepository.testConnection).
        let publicConfig = URLSessionConfiguration.ephemeral
        publicConfig.httpCookieStorage = nil
        publicConfig.timeoutIntervalForRequest = 15
        publicSession = URLSession(configuration: publicConfig)
    }

    // MARK: - Typed requests

    public func request<T: Decodable>(
        _ type: T.Type,
        _ method: String,
        _ path: String,
        query: [URLQueryItem] = [],
        headers: [String: String] = [:]
    ) async throws -> T {
        let request = try buildRequest(method, path, query: query, bodyData: nil, headers: headers)
        let (data, _) = try await perform(request, path: path)
        return try Self.decode(T.self, from: data)
    }

    public func request<T: Decodable, B: Encodable>(
        _ type: T.Type,
        _ method: String,
        _ path: String,
        query: [URLQueryItem] = [],
        body: B,
        headers: [String: String] = [:]
    ) async throws -> T {
        let bodyData = try Self.encoder.encode(body)
        let request = try buildRequest(method, path, query: query, bodyData: bodyData, headers: headers)
        let (data, _) = try await perform(request, path: path)
        return try Self.decode(T.self, from: data)
    }

    /// 2xx-or-throw request that ignores the response body.
    public func requestVoid(
        _ method: String,
        _ path: String,
        headers: [String: String] = [:]
    ) async throws {
        let request = try buildRequest(method, path, query: [], bodyData: nil, headers: headers)
        _ = try await perform(request, path: path)
    }

    public func requestVoid<B: Encodable>(
        _ method: String,
        _ path: String,
        body: B,
        headers: [String: String] = [:]
    ) async throws {
        let bodyData = try Self.encoder.encode(body)
        let request = try buildRequest(method, path, query: [], bodyData: bodyData, headers: headers)
        _ = try await perform(request, path: path)
    }

    /// Raw access for downloads/uploads (media, export archives, …).
    public func requestRaw(
        _ method: String,
        _ path: String,
        headers: [String: String] = [:]
    ) async throws -> (Data, HTTPURLResponse) {
        let request = try buildRequest(method, path, query: [], bodyData: nil, headers: headers)
        return try await perform(request, path: path)
    }

    public func requestRaw<B: Encodable>(
        _ method: String,
        _ path: String,
        body: B,
        headers: [String: String] = [:]
    ) async throws -> (Data, HTTPURLResponse) {
        let bodyData = try Self.encoder.encode(body)
        let request = try buildRequest(method, path, query: [], bodyData: bodyData, headers: headers)
        return try await perform(request, path: path)
    }

    // MARK: - Health check (login screen "test connection")

    /// Probes `GET {candidate}/health` with a cookieless session and returns a
    /// presentable success message, or throws an error carrying one.
    public func checkHealth(candidateAddress raw: String) async throws -> String {
        let base = ServerAddress.healthBase(for: raw)
        guard !base.isEmpty, let url = URL(string: base + "/health") else {
            throw APIError.serverNotConfigured
        }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 15
        request.setValue("LoveJournal-iOS/0.1.0", forHTTPHeaderField: "User-Agent")

        do {
            let (data, response) = try await publicSession.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw APIError.transport(.other("无有效响应"))
            }
            guard (200...299).contains(http.statusCode) else {
                if http.statusCode == 404 {
                    throw LoginError.message("服务器可达，但未找到健康检查接口（请确认端口为 :8000）")
                }
                throw APIError.http(status: http.statusCode, detail: APIError.serverDetail(from: data))
            }
            _ = try? Self.decode(AuthDTOs.HealthResponse.self, from: data)
            return "连接成功，后端运行正常"
        } catch let error as LoginError {
            throw error
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.transport(from: error)
        }
    }

    // MARK: - Plumbing

    private func buildRequest(
        _ method: String,
        _ path: String,
        query: [URLQueryItem],
        bodyData: Data?,
        headers: [String: String]
    ) throws -> URLRequest {
        let apiBase = baseURLProvider()
        guard !apiBase.isEmpty else { throw APIError.serverNotConfigured }
        guard var components = URLComponents(string: apiBase) else {
            throw APIError.serverNotConfigured
        }
        components.path = components.path + path
        components.queryItems = query.isEmpty ? nil : query
        guard let url = components.url else { throw APIError.serverNotConfigured }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = bodyData
        if bodyData != nil {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }
        return request
    }

    private func perform(_ request: URLRequest, path: String) async throws -> (Data, HTTPURLResponse) {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.transport(from: error)
        }
        guard let http = response as? HTTPURLResponse else {
            throw APIError.transport(.other("无有效响应"))
        }
        guard (200...299).contains(http.statusCode) else {
            let detail = APIError.serverDetail(from: data)
            if http.statusCode == 401 && !Self.exemptPaths.contains(where: { path.hasPrefix($0) }) {
                notifySessionExpired()
            }
            throw APIError.http(status: http.statusCode, detail: detail)
        }
        return (data, http)
    }

    private func notifySessionExpired() {
        guard let handler = onSessionExpired else { return }
        DispatchQueue.main.async {
            handler()
        }
    }

    /// Tolerant decoding: unknown JSON keys are ignored, dates accept both the
    /// plain and fractional-second ISO-8601 forms FastAPI may emit.
    public static func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let raw = try container.decode(String.self)
            if let date = Self.fractionalFormatter.date(from: raw) ?? Self.plainFormatter.date(from: raw) {
                return date
            }
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Unrecognized date string: \(raw)"
            )
        }
        do {
            return try decoder.decode(type, from: data)
        } catch {
            throw APIError.decoding(String(describing: error))
        }
    }

    public static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        return encoder
    }()

    private static let plainFormatter = ISO8601DateFormatter()
    private static let fractionalFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()
}
