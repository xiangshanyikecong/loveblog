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

/// Pure address normalization rules, ported 1:1 from the Android client
/// (`Android/.../data/remote/ServerAddress.kt`) so the two mobile clients
/// accept exactly the same input and derive exactly the same API base.
///
/// Direct backend deployments usually listen on :8000; reverse-proxy
/// deployments expose /api on the domain's default port instead.
public enum ServerAddress {
    public static let defaultPort = 8000

    // MARK: - Normalize

    /// Trims the input, infers the scheme and the API path/port.
    ///
    /// `https://demo.com`            → `https://demo.com/api/v1`
    /// `https://demo.com/api`        → `https://demo.com/api/v1`
    /// `http://192.168.1.5`          → `http://192.168.1.5:8000/v1`
    /// `192.168.1.5`                 → `https://192.168.1.5:8000/v1`
    /// `https://demo.com/love`       → `https://demo.com/love/v1`
    public static func normalize(_ raw: String) -> String {
        var value = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        while value.hasSuffix("/") {
            value.removeLast()
        }
        if value.isEmpty { return value }

        if !value.hasPrefix("http://") && !value.hasPrefix("https://") {
            value = "https://" + value
        }

        guard var components = URLComponents(string: value) else {
            // Unparseable input is returned as-is, mirroring the Android port.
            return value
        }

        let host = components.host ?? ""
        let originalSegments = pathSegments(of: components)
        let normalizedSegments = normalizeApiPath(host: host, port: components.port, segments: originalSegments)
        let explicitPort = hasExplicitPort(components)
        let backendPort = shouldUseBackendPort(host: host, segments: normalizedSegments)

        var port: Int?
        if explicitPort {
            port = components.port
        } else if backendPort {
            port = defaultPort
        }

        components.port = (port != nil && port != schemeDefaultPort(components.scheme)) ? port : nil
        components.path = normalizedSegments.isEmpty ? "/" : "/" + normalizedSegments.joined(separator: "/")
        components.query = nil
        components.fragment = nil

        let normalized = components.string ?? value
        return normalized.hasSuffix("/") ? String(normalized.dropLast()) : normalized
    }

    // MARK: - Stripping

    /// Removes a trailing `/v1` (keeping any `/api` prefix) for display and
    /// health-check bases.
    public static func stripApiVersion(_ value: String) -> String {
        if value.lowercased().hasSuffix("/v1") {
            return String(value.dropLast("/v1".count)).trimmingTrailingSlashes
        }
        return value.trimmingTrailingSlashes
    }

    /// Removes the whole `/api/v1` suffix, yielding the origin used for media.
    public static func stripMediaApiPrefix(_ value: String) -> String {
        let lowered = value.lowercased()
        if lowered.hasSuffix("/api/v1") {
            return String(value.dropLast("/api/v1".count)).trimmingTrailingSlashes
        }
        if lowered.hasSuffix("/v1") {
            return String(value.dropLast("/v1".count)).trimmingTrailingSlashes
        }
        return value.trimmingTrailingSlashes
    }

    // MARK: - Validation

    /// Validates user input before login. Returns an error message or nil if OK.
    /// Mirrors the Android wording so both clients speak the same language.
    public static func validateAddressInput(_ raw: String, allowCleartext: Bool) -> String? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return "请输入服务器地址" }
        if !trimmed.hasPrefix("http://") && !trimmed.hasPrefix("https://") {
            return "请填写完整的 https:// 服务器地址"
        }
        guard let components = URLComponents(string: trimmed), components.host != nil else {
            return "服务器地址格式不正确"
        }
        let isHTTPS = components.scheme?.lowercased() == "https"
        if !isHTTPS && (!allowCleartext || !isLocalDevelopmentHost(components.host ?? "")) {
            return "为保护账号和会话，正式版仅允许 HTTPS；本地 HTTP 仅限调试版私有地址"
        }
        return nil
    }

    /// Health/base URL for a candidate address without persisting it:
    /// `https://demo.com/api/v1` → `https://demo.com/api`.
    public static func healthBase(for raw: String) -> String {
        stripApiVersion(normalize(raw))
    }

    // MARK: - Host classification

    public static func isLocalDevelopmentHost(_ host: String) -> Bool {
        let lowered = host.lowercased()
        if lowered == "localhost" || lowered == "10.0.2.2" || lowered == "::1" { return true }
        let octets = lowered.split(separator: ".").compactMap { Int($0) }
        guard octets.count == 4, octets.allSatisfy({ (0...255).contains($0) }) else { return false }
        return octets[0] == 10 ||
            (octets[0] == 172 && (16...31).contains(octets[1])) ||
            (octets[0] == 192 && octets[1] == 168) ||
            octets[0] == 127
    }

    // MARK: - Private helpers

    private static func pathSegments(of components: URLComponents) -> [String] {
        components.path.split(separator: "/", omittingEmptySubsequences: true).map(String.init)
    }

    private static func normalizeApiPath(host: String, port: Int?, segments: [String]) -> [String] {
        if segments.isEmpty {
            return shouldUseProxyPath(host: host, port: port) ? ["api", "v1"] : ["v1"]
        }
        if segments.count == 1 && segments[0].lowercased() == "api" {
            return ["api", "v1"]
        }
        if segments.last?.lowercased() == "v1" {
            return segments
        }
        return segments + ["v1"]
    }

    private static func shouldUseProxyPath(host: String, port: Int?) -> Bool {
        let lowered = host.lowercased()
        if port == defaultPort { return false }
        if lowered == "10.0.2.2" { return false }
        if lowered == "localhost" { return false }
        if isIPLiteral(lowered) { return false }
        if !lowered.contains(".") { return false }
        return true
    }

    private static func shouldUseBackendPort(host: String, segments: [String]) -> Bool {
        let lowered = host.lowercased()
        if segments.first?.lowercased() == "api" { return false }
        if lowered == "10.0.2.2" { return true }
        if lowered == "localhost" { return true }
        if isIPLiteral(lowered) { return true }
        return !lowered.contains(".")
    }

    private static func hasExplicitPort(_ components: URLComponents) -> Bool {
        guard let port = components.port else { return false }
        return port != schemeDefaultPort(components.scheme)
    }

    private static func schemeDefaultPort(_ scheme: String?) -> Int {
        scheme?.lowercased() == "https" ? 443 : 80
    }

    private static func isIPLiteral(_ host: String) -> Bool {
        if host.hasPrefix("[") && host.hasSuffix("]") { return true }
        return isIPv4(host)
    }

    private static func isIPv4(_ host: String) -> Bool {
        let parts = host.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count == 4 else { return false }
        return parts.allSatisfy { part in
            guard !part.isEmpty, part.count <= 3, part.allSatisfy(\.isNumber) else { return false }
            return (0...255).contains(Int(part) ?? -1)
        }
    }
}

private extension String {
    var trimmingTrailingSlashes: String {
        var value = self
        while value.hasSuffix("/") { value.removeLast() }
        return value
    }
}
