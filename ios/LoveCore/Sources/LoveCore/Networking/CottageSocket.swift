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

/// Generic realtime socket for the cottage endpoints (chat / listen / watch).
///
/// Protocol (mirrors Android `CottageWebSocket.kt`):
/// - frames are `{"type": "...", "payload": {...}}`; server frames may add
///   `event_seq` / `origin_uid` / `server_ts_ms` metadata;
/// - PING every 25s (`{"type":"PING"}`), server answers PONG (swallowed);
/// - reconnect with exponential backoff `min(30s, 1s * 2^attempts)`;
/// - close codes 4401/4403 are terminal (auth rejected → no reconnect).
///
/// Auth rides the shared `HTTPCookieStorage` `access_token` cookie (the
/// URLSession sends cookies on the WS upgrade); a bearer header may be
/// supplied as fallback.
public final class CottageSocket: NSObject, @unchecked Sendable {
    public struct Frame {
        public let type: String
        public let payload: [String: Any]?
        public let eventSeq: Int?
        public let originUid: String?
    }

    public var onOpen: (() -> Void)?
    public var onFrame: ((Frame) -> Void)?
    public var onClose: ((Int) -> Void)?
    public var onError: ((Error) -> Void)?

    private let makeURL: () -> URL?
    private let bearerToken: (() -> String?)?
    private var task: URLSessionWebSocketTask?
    private var session: URLSession?
    private var pingTimer: Timer?
    private var reconnectAttempts = 0
    private var manuallyClosed = false
    private let queue = DispatchQueue(label: "com.lovejournal.cottagesocket")

    public init(makeURL: @escaping () -> URL?, bearerToken: (() -> String?)? = nil) {
        self.makeURL = makeURL
        self.bearerToken = bearerToken
    }

    public func connect() {
        queue.async { [weak self] in
            guard let self else { return }
            self.manuallyClosed = false
            self.openSocket()
        }
    }

    public func close() {
        queue.async { [weak self] in
            guard let self else { return }
            self.manuallyClosed = true
            self.teardownSocket()
        }
    }

    /// Sends a `{"type":..., "payload":...}` frame (payload may be nil).
    public func send(type: String, payload: [String: Any]? = nil) {
        queue.async { [weak self] in
            guard let self, let task = self.task else { return }
            var frame: [String: Any] = ["type": type]
            if let payload { frame["payload"] = payload }
            guard let data = try? JSONSerialization.data(withJSONObject: frame),
                  let text = String(data: data, encoding: .utf8)
            else { return }
            task.send(.string(text)) { _ in }
        }
    }

    // MARK: - Internals

    private func openSocket() {
        guard let url = makeURL() else {
            DispatchQueue.main.async { self.onError?(ChatCryptoError.badBase64("ws-url")) }
            return
        }
        var request = URLRequest(url: url)
        if let token = bearerToken?(), !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        let session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
        self.session = session
        let task = session.webSocketTask(with: request)
        self.task = task
        task.resume()
        receiveLoop()
    }

    private func teardownSocket() {
        pingTimer?.invalidate()
        pingTimer = nil
        task?.cancel(with: .normalClosure, reason: nil)
        task = nil
        session?.invalidateAndCancel()
        session = nil
    }

    private func receiveLoop() {
        task?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let message):
                self.queue.async {
                    self.handle(message: message)
                    self.receiveLoop()
                }
            case .failure(let error):
                self.queue.async {
                    self.handleFailure(error)
                }
            }
        }
    }

    private func handle(message: URLSessionWebSocketTask.Message) {
        guard case .string(let text) = message,
              let data = text.data(using: .utf8),
              let raw = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = raw["type"] as? String
        else { return }
        if type == "PONG" { return }
        let frame = Frame(
            type: type,
            payload: raw["payload"] as? [String: Any],
            eventSeq: raw["event_seq"] as? Int,
            originUid: raw["origin_uid"] as? String
        )
        DispatchQueue.main.async { self.onFrame?(frame) }
    }

    private func handleFailure(_ error: Error) {
        teardownSocket()
        if manuallyClosed {
            DispatchQueue.main.async { self.onClose?(0) }
            return
        }
        // Real close codes surface via the `didCloseWith` delegate callback;
        // transport failures here always qualify for a reconnect attempt.
        scheduleReconnect()
        DispatchQueue.main.async { self.onError?(error) }
    }

    private func scheduleReconnect() {
        let delay = min(30.0, 1.0 * pow(2.0, Double(reconnectAttempts)))
        reconnectAttempts += 1
        queue.asyncAfter(deadline: .now() + delay) { [weak self] in
            guard let self, !self.manuallyClosed else { return }
            self.openSocket()
        }
    }

    private func startPing() {
        pingTimer?.invalidate()
        let timer = Timer(timeInterval: 25, repeats: true) { [weak self] _ in
            self?.send(type: "PING")
        }
        pingTimer = timer
        DispatchQueue.main.async { RunLoop.main.add(timer, forMode: .common) }
    }
}

extension CottageSocket: URLSessionWebSocketDelegate {
    public func urlSession(
        _ session: URLSession,
        webSocketTask: URLSessionWebSocketTask,
        didOpenWithProtocol protocol: String?
    ) {
        queue.async { [weak self] in
            guard let self else { return }
            self.reconnectAttempts = 0
            self.startPing()
            DispatchQueue.main.async { self.onOpen?() }
        }
    }

    public func urlSession(
        _ session: URLSession,
        webSocketTask: URLSessionWebSocketTask,
        didCloseWith closeCode: URLSessionWebSocketTask.CloseCode,
        reason: Data?
    ) {
        queue.async { [weak self] in
            guard let self else { return }
            self.teardownSocket()
            let code = closeCode.rawValue
            if !self.manuallyClosed && code != 4401 && code != 4403 {
                self.scheduleReconnect()
            }
            DispatchQueue.main.async { self.onClose?(code) }
        }
    }
}
