import SwiftUI
import UIKit

/// Airline logo marks (#60), so a commercial flight reads at a glance. None
/// is shipped: an airline's logo is its trademark. The app fetches the
/// airline's own site icon at run time (Google's favicon service first, which
/// serves most sites' touch icons at a usable size; DuckDuckGo's as the
/// fallback), keeps it on the phone, and shows it beside the airline's name.
/// Nothing about the owner is sent: the request names the airline's domain
/// and nothing else.
enum AirlineLogos {
    /// A setting, shared with the notification extension through the app
    /// group: the marks come from icon services with no published terms
    /// (Google's, DuckDuckGo's), and an airline's mark is its trademark,
    /// used here only to say which airline it is. A build meant for sale
    /// ships with `defaultOn` false until marks with clear rights exist;
    /// off, labels and alerts show the airline's name alone.
    static let defaultOn = true
    static let settingKey = "stratoscan.airlineMarks"
    static var defaults: UserDefaults { UserDefaults(suiteName: "group.com.NelsonIndustries.radome") ?? .standard }
    static var enabled: Bool {
        get { defaults.object(forKey: settingKey) as? Bool ?? defaultOn }
        set { defaults.set(newValue, forKey: settingKey) }
    }

    /// Where the mark for a domain can be fetched, in order of preference.
    static func urls(for domain: String) -> [URL] {
        [URL(string: "https://www.google.com/s2/favicons?domain=\(domain)&sz=128"),
         URL(string: "https://icons.duckduckgo.com/ip3/\(domain).ico")].compactMap { $0 }
    }

    /// The airline for a callsign ("DAL1234" → Delta), when it is one.
    static func airline(forCallsign cs: String?) -> Airline? {
        guard let cs = cs?.trimmingCharacters(in: .whitespaces), cs.count >= 4,
              cs.range(of: #"^[A-Z]{3}\d"#, options: .regularExpression) != nil else { return nil }
        return AirlineTable.byICAO[String(cs.prefix(3))]
    }

    /// Downloads a mark, trying each source; nil when none has one.
    static func fetch(domain: String) async -> UIImage? {
        guard enabled else { return nil }
        let dir = cacheDir
        let file = dir.appendingPathComponent(domain + ".png")
        if let data = try? Data(contentsOf: file), let img = UIImage(data: data) { return img }
        for url in urls(for: domain) {
            var req = URLRequest(url: url, timeoutInterval: 8)
            req.setValue("StratoScan/1.0 (iOS app)", forHTTPHeaderField: "User-Agent")
            guard let (data, resp) = try? await URLSession.shared.data(for: req),
                  (resp as? HTTPURLResponse)?.statusCode == 200,
                  let img = UIImage(data: data), img.size.width >= 32 else { continue }
            // Google answers a generic globe for a site it has no icon for;
            // that is 16 px, and skipped above.
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            try? (img.pngData() ?? data).write(to: file)
            return img
        }
        return nil
    }

    private static var cacheDir: URL {
        (FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first ?? FileManager.default.temporaryDirectory)
            .appendingPathComponent("airline-logos", isDirectory: true)
    }
}

/// The marks the radar has fetched so far, by ICAO code, for the labels
/// (drawn in a Canvas, which needs them ready) and the details.
@MainActor
final class AirlineLogoStore: ObservableObject {
    static let shared = AirlineLogoStore()
    @Published private(set) var marks: [String: UIImage] = [:]
    private var pending: Set<String> = []
    private var missing: Set<String> = []

    /// The mark for an airline, if it has been fetched; asks for it otherwise.
    func mark(for icao: String?) -> UIImage? {
        guard let icao, let a = AirlineTable.byICAO[icao], let domain = a.domain else { return nil }
        if let m = marks[icao] { return m }
        guard !pending.contains(icao), !missing.contains(icao) else { return nil }
        pending.insert(icao)
        Task {
            let img = await AirlineLogos.fetch(domain: domain)
            pending.remove(icao)
            if let img { marks[icao] = img } else { missing.insert(icao) }
        }
        return nil
    }
}
