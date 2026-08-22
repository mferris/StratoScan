import Foundation

enum AircraftFeedClient {
    static func fetchAircraft() async throws -> [RawAircraft] {
        var req = URLRequest(url: APIConfig.url("/tar1090/data/aircraft.json"))
        req.cachePolicy = .reloadIgnoringLocalCacheData
        let (data, response) = try await URLSession.shared.data(for: req)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(AircraftFeedResponse.self, from: data).aircraft
    }

    static func fetchReceiver() async throws -> Coordinate? {
        var req = URLRequest(url: APIConfig.url("/tar1090/data/receiver.json"))
        req.cachePolicy = .reloadIgnoringLocalCacheData
        let (data, response) = try await URLSession.shared.data(for: req)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        let r = try JSONDecoder().decode(ReceiverResponse.self, from: data)
        guard let lat = r.lat, let lon = r.lon else { return nil }
        return Coordinate(lat: lat, lon: lon)
    }
}
