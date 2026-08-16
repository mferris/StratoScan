import Foundation

/// ADS-B carries no aircraft type/model info directly. tar1090 (already
/// installed alongside readsb on the Pi) ships its own local hex ->
/// [registration, icaoType, flags, typeLong] database, split into a prefix
/// trie of small same-origin JSON files. We read that same data directly
/// (not tar1090's code — its own license is unclear ["Other"/NOASSERTION on
/// GitHub] — this is a fresh implementation reading the same public data
/// files, mirroring the web version's lookupType()).
actor AircraftTypeClient {
    private var databaseFolder: String?
    private var typeCodeTable: [String: String] = [:]
    private var shardCache: [String: Task<[String: JSONValue]?, Never>] = [:]
    private var hexTypeCache: [String: String?] = [:]

    func warmUp() async {
        await discoverDatabaseFolder()
        await loadTypeCodeTable()
    }

    private func discoverDatabaseFolder() async {
        do {
            let (data, _) = try await URLSession.shared.data(from: APIConfig.url("/tar1090/index.html"))
            guard let html = String(data: data, encoding: .utf8) else { return }
            if let range = html.range(of: #"databaseFolder\s*=\s*"([^"]+)""#, options: .regularExpression) {
                let match = String(html[range])
                if let quoteRange = match.range(of: #""[^"]+""#, options: .regularExpression) {
                    databaseFolder = String(match[quoteRange]).replacingOccurrences(of: "\"", with: "")
                }
            }
        } catch {
            // type lookups just stay disabled; everything else still works
        }
    }

    private func loadTypeCodeTable() async {
        guard let databaseFolder else { return }
        do {
            let (data, _) = try await URLSession.shared.data(from: APIConfig.url("/tar1090/\(databaseFolder)/icao_aircraft_types2.js"))
            guard let dict = try JSONSerialization.jsonObject(with: data) as? [String: [Any]] else { return }
            for (code, entry) in dict {
                if let typeLong = entry.first as? String {
                    typeCodeTable[code] = Self.humanize(typeLong)
                }
            }
        } catch {
            // fine — per-hex typeLong (below) still covers most aircraft on its own
        }
    }

    /// "CIRRUS SR-22" -> "Cirrus SR-22": only re-cases words that are ALL
    /// CAPS (manufacturer names), leaving model numbers like "SR-22" as-is.
    private static func humanize(_ s: String) -> String {
        s.split(separator: " ").map { word -> String in
            let w = String(word)
            guard w.uppercased() == w, w.rangeOfCharacter(from: .letters) != nil else { return w }
            return w.prefix(1) + w.dropFirst().lowercased()
        }.joined(separator: " ")
    }

    private func fetchShard(_ bkey: String) async -> [String: JSONValue]? {
        if let task = shardCache[bkey] { return await task.value }
        guard let databaseFolder else { return nil }
        let task = Task<[String: JSONValue]?, Never> {
            do {
                let (data, _) = try await URLSession.shared.data(from: APIConfig.url("/tar1090/\(databaseFolder)/\(bkey).js"))
                return try JSONDecoder().decode([String: JSONValue].self, from: data)
            } catch {
                return nil
            }
        }
        shardCache[bkey] = task
        return await task.value
    }

    /// Walks the same prefix-trie structure tar1090 stores its hex database
    /// in: each shard either has the remaining hex suffix as a direct key,
    /// or a "children" list naming deeper shards to descend into.
    func lookupType(hex: String) async -> String? {
        if let cached = hexTypeCache[hex] { return cached }
        guard databaseFolder != nil else { return nil }

        let icao = hex.uppercased()
        var level = 1
        var entry: JSONValue?

        while level <= icao.count {
            let bkey = String(icao.prefix(level))
            guard let data = await fetchShard(bkey) else { break }
            let dkey = String(icao.dropFirst(level))
            if let found = data[dkey] {
                entry = found
                break
            }
            if case .array(let children)? = data["children"],
               let nextChar = dkey.first,
               children.contains(.string(bkey + String(nextChar))) {
                level += 1
                continue
            }
            break
        }

        var label: String?
        if case .array(let arr)? = entry, arr.count >= 4 {
            if case .string(let typeLong) = arr[3], !typeLong.isEmpty {
                label = Self.humanize(typeLong)
            } else if case .string(let typeCode) = arr[1] {
                label = typeCodeTable[typeCode.uppercased()]
            }
        }

        hexTypeCache[hex] = label
        return label
    }
}

/// Minimal untyped JSON value — the hex-db shard entries are heterogeneous
/// arrays ([String, String, String, String] with possible nulls), and
/// "children" is an array of strings alongside them in the same object.
enum JSONValue: Decodable, Equatable {
    case string(String)
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let s = try? c.decode(String.self) { self = .string(s); return }
        if let a = try? c.decode([JSONValue].self) { self = .array(a); return }
        self = .null
    }
}
