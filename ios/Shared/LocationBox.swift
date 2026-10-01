import CryptoKit
import Foundation

/// The phone's location, sealed so that only one radar can read it (roadmap
/// 2.7: alerts for aircraft approaching where the phone is). The relay
/// carries the result and can't read it; deploy/events.py opens it.
///
/// The radar publishes an X25519 "box" key, signed by its Ed25519 identity:
/// the radar id the phone scanned when pairing. The phone checks that
/// signature before using the key, so the relay can't substitute its own.
///
/// A blob is base64url(ephemeral X25519 public key (32) | ChaCha20-Poly1305
/// combined box: nonce (12), ciphertext, tag (16)). The key is HKDF-SHA256 of
/// the shared secret, info "stratoscan-location-v1" + ephemeral key + the
/// radar's box key; the phone's id is the associated data. Inside:
/// {"lat", "lon", "ts"}. tests/test_phone_approach.py checks a blob made here.
enum LocationBox {
    static let boxKeyContext = "stratoscan-boxkey-v1:"
    static let info = Data("stratoscan-location-v1".utf8)

    /// The radar's box key, if its signature checks out against the radar's id.
    static func verifiedBoxKey(unit: String, key: String, sig: String) -> Curve25519.KeyAgreement.PublicKey? {
        guard let idRaw = Data(base64url: unit), let keyRaw = Data(base64url: key), let sigRaw = Data(base64url: sig),
              let identity = try? Curve25519.Signing.PublicKey(rawRepresentation: idRaw),
              identity.isValidSignature(sigRaw, for: Data((boxKeyContext + key).utf8))
        else { return nil }
        return try? Curve25519.KeyAgreement.PublicKey(rawRepresentation: keyRaw)
    }

    /// `lat`/`lon` sealed to one radar, for one phone (its relay id).
    static func seal(lat: Double, lon: Double, ts: Int, to box: Curve25519.KeyAgreement.PublicKey, phone: String) throws -> String {
        let ephemeral = Curve25519.KeyAgreement.PrivateKey()
        let shared = try ephemeral.sharedSecretFromKeyAgreement(with: box)
        let ephemeralRaw = ephemeral.publicKey.rawRepresentation
        let key = shared.hkdfDerivedSymmetricKey(using: SHA256.self, salt: Data(),
                                                 sharedInfo: info + ephemeralRaw + box.rawRepresentation,
                                                 outputByteCount: 32)
        let plain = try JSONSerialization.data(withJSONObject: ["lat": lat, "lon": lon, "ts": ts])
        let sealed = try ChaChaPoly.seal(plain, using: key, authenticating: Data(phone.utf8))
        return (ephemeralRaw + sealed.combined).base64urlString
    }
}

extension Data {
    init?(base64url s: String) {
        var b = s.replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        b += String(repeating: "=", count: (4 - b.count % 4) % 4)
        self.init(base64Encoded: b)
    }

    var base64urlString: String {
        base64EncodedString().replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
    }
}
