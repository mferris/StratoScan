import Foundation
import Network

/// Finds a paired radar on the home network after its address has changed
/// (#76). Every radar advertises `_stratoscan._tcp` (deploy/avahi-stratoscan.service);
/// this browses for it, asks each radar found who it is (the LAN-only
/// `/setup/api/hello` carries its unit id, a public fact), and returns the
/// first that is paired with this phone. Seen on 2026-10-23: the router gave
/// RDU a new address after its card was rebuilt, and the app sat on the old
/// one, out of reach, until the owner retyped it.
enum RadarFinder {
    /// The home address ("http://<IPv4>") of a paired radar, or nil. Also
    /// records the address on the paired radar, so Settings shows it.
    static func find(pairing: PairingStore, timeout: TimeInterval = 4) async -> String? {
        let units = await MainActor.run { Set(pairing.radars.map(\.unit)) }
        guard !units.isEmpty else { return nil }
        for host in await browse(timeout: timeout) {
            if let unit = await helloUnit(host), units.contains(unit) {
                await MainActor.run { pairing.setHost(host, unit: unit) }
                return "http://\(host)"
            }
        }
        return nil
    }

    /// The IPv4 address of every `_stratoscan._tcp` service seen within the
    /// timeout. IPv4 only: an IPv6 link-local address needs a scope id that a
    /// URL cannot carry.
    private static func browse(timeout: TimeInterval) async -> [String] {
        await withCheckedContinuation { (cont: CheckedContinuation<[String], Never>) in
            let queue = DispatchQueue(label: "stratoscan.finder")
            let state = BrowseState()
            let browser = NWBrowser(for: .bonjour(type: "_stratoscan._tcp", domain: nil), using: .tcp)
            let finish = {
                guard !state.done else { return }
                state.done = true
                browser.cancel()
                state.connections.forEach { $0.cancel() }
                cont.resume(returning: state.found)
            }
            browser.browseResultsChangedHandler = { results, _ in
                for result in results where !state.seen.contains(result.endpoint) {
                    state.seen.insert(result.endpoint)
                    let tcp = NWParameters.tcp
                    if let ip = tcp.defaultProtocolStack.internetProtocol as? NWProtocolIP.Options { ip.version = .v4 }
                    let connection = NWConnection(to: result.endpoint, using: tcp)
                    state.connections.append(connection)
                    connection.stateUpdateHandler = { s in
                        guard case .ready = s else { return }
                        if case let .hostPort(host, _)? = connection.currentPath?.remoteEndpoint,
                           case let .ipv4(address) = host {
                            let text = "\(address)"
                            if !state.found.contains(text) { state.found.append(text) }
                        }
                        connection.cancel()
                    }
                    connection.start(queue: queue)
                }
            }
            browser.stateUpdateHandler = { s in
                if case .failed = s { finish() }
            }
            browser.start(queue: queue)
            queue.asyncAfter(deadline: .now() + timeout) { finish() }
        }
    }

    /// Who answers at this address: the unit id from its LAN-only hello.
    private static func helloUnit(_ host: String) async -> String? {
        struct Hello: Decodable { let unit: String? }
        guard let url = URL(string: "http://\(host)/setup/api/hello") else { return nil }
        let req = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 2)
        guard let (data, resp) = try? await URLSession.shared.data(for: req),
              (resp as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return (try? JSONDecoder().decode(Hello.self, from: data))?.unit
    }
}

/// The browse's working state, touched only on its own serial queue.
private final class BrowseState: @unchecked Sendable {
    var done = false
    var found: [String] = []
    var seen = Set<NWEndpoint>()
    var connections: [NWConnection] = []
}
