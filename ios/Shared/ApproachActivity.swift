import ActivityKit
import Foundation

/// A Live Activity for an aircraft about to pass over (roadmap 2.4). Started
/// by the Radome relay with a push-to-start push when the radar predicts a
/// close pass, and ended by it after the pass. The field names are the JSON
/// keys the relay sends (relay/src/apns.js approachStart/approachEnd).
struct ApproachAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        /// When the aircraft is expected overhead (unix seconds).
        var etaUnix: Double
        var passed: Bool
        var altFt: Int?
        var distNm: Double?
        var dir: String?

        var eta: Date { Date(timeIntervalSince1970: etaUnix) }
    }

    var unit: String
    var hex: String
    var callsign: String
    var type: String
    var reason: String
}
