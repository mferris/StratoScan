import UIKit

/// What a radar calls this phone in its list of paired phones.
///
/// It was `UIDevice.current.name`, and since iOS 16 that is the same word on
/// every phone: "iPhone" (the name its owner gave it is kept from apps). A
/// radar with two phones paired listed "iPhone" twice, and the one to unpair
/// could only be told by its date (2026-11-15). Now it is the phone's model
/// ("iPhone 16 Pro"), or a name its owner types in Settings for two of the
/// same model. It goes to the relay at pairing and again whenever the phone
/// registers for alerts, so a phone paired before this is renamed without
/// pairing again.
enum PhoneName {
    private static let key = "stratoscan.phoneName"

    /// The name typed in Settings, if any.
    static var custom: String? {
        get { UserDefaults.standard.string(forKey: key).flatMap(clean) }
        set {
            if let v = newValue.flatMap(clean) { UserDefaults.standard.set(v, forKey: key) }
            else { UserDefaults.standard.removeObject(forKey: key) }
        }
    }

    /// The name sent: the typed one, else the model.
    static var current: String { custom ?? model }

    /// As the relay keeps it (cleanPhoneName): its control characters out,
    /// and 40 UTF-16 units at most, which is how the relay counts. Whole
    /// characters are dropped from the end, so an emoji is never cut in two,
    /// and what is shown here is what the radar shows. Joiners and the like
    /// stay: a name's letters and emoji can depend on them.
    static func clean(_ s: String) -> String? {
        let control: (Unicode.Scalar) -> Bool = { $0.value <= 0x1F || (0x7F...0x9F).contains($0.value) || $0.value == 0x2028 || $0.value == 0x2029 }
        var t = String(String.UnicodeScalarView(s.unicodeScalars.filter { !control($0) })).trimmingCharacters(in: .whitespacesAndNewlines)
        while t.utf16.count > 40 { t.removeLast() }
        t = t.trimmingCharacters(in: .whitespacesAndNewlines)
        return t.isEmpty ? nil : t
    }

    /// "iPhone 16 Pro"; for a model newer than this list, what iOS calls the
    /// kind of device ("iPhone", "iPad").
    static var model: String { name(for: identifier) ?? UIDevice.current.model }

    /// Apple's identifier for the hardware ("iPhone17,1"); a simulator gives
    /// the one it stands in for.
    static var identifier: String {
        if let sim = ProcessInfo.processInfo.environment["SIMULATOR_MODEL_IDENTIFIER"] { return sim }
        var size = 0
        sysctlbyname("hw.machine", nil, &size, nil, 0)
        var buf = [CChar](repeating: 0, count: max(size, 1))
        sysctlbyname("hw.machine", &buf, &size, nil, 0)
        return String(cString: buf)
    }

    static func name(for identifier: String) -> String? { models[identifier] }

    /// The iPhones and iPads that run this app's iOS (17.2 and later), as
    /// Xcode's own device list names them (one identifier per model there;
    /// a cellular or regional variant with another identifier, or a model
    /// newer than this list, sends "iPhone" or "iPad" until it is added or
    /// its owner types a name).
    static let models: [String: String] = [
        "iPhone11,2": "iPhone XS", "iPhone11,4": "iPhone XS Max", "iPhone11,6": "iPhone XS Max", "iPhone11,8": "iPhone XR",
        "iPhone12,1": "iPhone 11", "iPhone12,3": "iPhone 11 Pro", "iPhone12,5": "iPhone 11 Pro Max",
        "iPhone12,8": "iPhone SE (2nd generation)",
        "iPhone13,1": "iPhone 12 mini", "iPhone13,2": "iPhone 12", "iPhone13,3": "iPhone 12 Pro", "iPhone13,4": "iPhone 12 Pro Max",
        "iPhone14,2": "iPhone 13 Pro", "iPhone14,3": "iPhone 13 Pro Max", "iPhone14,4": "iPhone 13 mini", "iPhone14,5": "iPhone 13",
        "iPhone14,6": "iPhone SE (3rd generation)", "iPhone14,7": "iPhone 14", "iPhone14,8": "iPhone 14 Plus",
        "iPhone15,2": "iPhone 14 Pro", "iPhone15,3": "iPhone 14 Pro Max", "iPhone15,4": "iPhone 15", "iPhone15,5": "iPhone 15 Plus",
        "iPhone16,1": "iPhone 15 Pro", "iPhone16,2": "iPhone 15 Pro Max",
        "iPhone17,1": "iPhone 16 Pro", "iPhone17,2": "iPhone 16 Pro Max", "iPhone17,3": "iPhone 16", "iPhone17,4": "iPhone 16 Plus",
        "iPhone17,5": "iPhone 16e",
        "iPhone18,1": "iPhone 17 Pro", "iPhone18,2": "iPhone 17 Pro Max", "iPhone18,3": "iPhone 17", "iPhone18,4": "iPhone Air",
        "iPhone18,5": "iPhone 17e",
        "iPhone19,2": "iPhone 18 Pro", "iPhone19,3": "iPhone 18 Pro Max", "iPhone19,4": "iPhone Duo",
        "iPad7,1": "iPad Pro (12.9-inch) (2nd generation)", "iPad7,3": "iPad Pro (10.5-inch)",
        "iPad7,6": "iPad (6th generation)", "iPad7,12": "iPad (7th generation)",
        "iPad8,1": "iPad Pro (11-inch) (1st generation)", "iPad8,5": "iPad Pro (12.9-inch) (3rd generation)",
        "iPad8,9": "iPad Pro (11-inch) (2nd generation)", "iPad8,12": "iPad Pro (12.9-inch) (4th generation)",
        "iPad11,1": "iPad mini (5th generation)", "iPad11,3": "iPad Air (3rd generation)", "iPad11,7": "iPad (8th generation)",
        "iPad12,2": "iPad (9th generation)", "iPad13,2": "iPad Air (4th generation)",
        "iPad13,5": "iPad Pro (11-inch) (3rd generation)", "iPad13,10": "iPad Pro (12.9-inch) (5th generation)",
        "iPad13,17": "iPad Air (5th generation)", "iPad13,18": "iPad (10th generation)",
        "iPad14,1": "iPad mini (6th generation)", "iPad14,3": "iPad Pro (11-inch) (4th generation)",
        "iPad14,5": "iPad Pro (12.9-inch) (6th generation)", "iPad14,9": "iPad Air 11-inch (M2)",
        "iPad14,11": "iPad Air 13-inch (M2)", "iPad15,3": "iPad Air 11-inch (M3)", "iPad15,5": "iPad Air 13-inch (M3)",
        "iPad15,7": "iPad (A16)", "iPad16,2": "iPad mini (A17 Pro)", "iPad16,4": "iPad Pro 11-inch (M4)",
        "iPad16,6": "iPad Pro 13-inch (M4)", "iPad16,9": "iPad Air 11-inch (M4)", "iPad16,11": "iPad Air 13-inch (M4)",
        "iPad17,2": "iPad Pro 11-inch (M5)", "iPad17,4": "iPad Pro 13-inch (M5)", "iPad19,2": "iPad mini (A20 Pro)",
    ]
}
