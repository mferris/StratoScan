import CryptoKit
import Foundation
import Security

/// This phone's identity with the StratoScan relay: an Ed25519 key made on the
/// phone and kept in its Keychain, never synced or backed up. Its public key
/// is the phone's id -- the same scheme units use (deploy/heartbeat.py,
/// relay/src/auth.js), so the relay verifies both the same way.
enum RelayIdentity {
    private static let service = "radome.relay.identity"
    private static let account = "phone-signing-key"

    enum Failure: LocalizedError {
        case keychain(OSStatus)
        var errorDescription: String? {
            if case .keychain(let s) = self { return "Could not use the Keychain (\(s))." }
            return nil
        }
    }

    static func key() throws -> Curve25519.Signing.PrivateKey {
        if let raw = try load() {
            return try Curve25519.Signing.PrivateKey(rawRepresentation: raw)
        }
        let key = Curve25519.Signing.PrivateKey()
        try store(key.rawRepresentation)
        return key
    }

    static func id() throws -> String {
        base64url(try key().publicKey.rawRepresentation)
    }

    /// The headers for one request. The signed message binds the time,
    /// method, path and body: `ts\nMETHOD\npath\nsha256hex(body)`.
    static func headers(method: String, path: String, body: Data, now: Date = Date(),
                        key given: Curve25519.Signing.PrivateKey? = nil) throws -> [String: String] {
        let key = try given ?? key()
        let ts = String(Int(now.timeIntervalSince1970))
        let hash = SHA256.hash(data: body).map { String(format: "%02x", $0) }.joined()
        let message = "\(ts)\n\(method.uppercased())\n\(path)\n\(hash)"
        let sig = try key.signature(for: Data(message.utf8))
        return ["X-FR-Phone": base64url(key.publicKey.rawRepresentation),
                "X-FR-Time": ts,
                "X-FR-Sig": base64url(sig)]
    }

    static func base64url(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    private static func load() throws -> Data? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                    kSecAttrService as String: service,
                                    kSecAttrAccount as String: account,
                                    kSecReturnData as String: true]
        var out: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &out)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess else { throw Failure.keychain(status) }
        return out as? Data
    }

    private static func store(_ raw: Data) throws {
        let item: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                   kSecAttrService as String: service,
                                   kSecAttrAccount as String: account,
                                   kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
                                   kSecValueData as String: raw]
        let status = SecItemAdd(item as CFDictionary, nil)
        guard status == errSecSuccess else { throw Failure.keychain(status) }
    }
}
