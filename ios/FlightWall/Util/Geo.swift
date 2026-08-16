import Foundation

enum Geo {
    struct BearingRange {
        let bearing: Double
        let range: Double // nautical miles
    }

    static func haversineBearingRange(lat1: Double, lon1: Double, lat2: Double, lon2: Double) -> BearingRange {
        let toRad = { (d: Double) in d * .pi / 180 }
        let phi1 = toRad(lat1), phi2 = toRad(lat2)
        let dLambda = toRad(lon2 - lon1)

        let y = sin(dLambda) * cos(phi2)
        let x = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dLambda)
        let bearing = (atan2(y, x) * 180 / .pi + 360).truncatingRemainder(dividingBy: 360)

        let rNm = 3440.065
        let dPhi = toRad(lat2 - lat1)
        let a = sin(dPhi / 2) * sin(dPhi / 2) + cos(phi1) * cos(phi2) * sin(dLambda / 2) * sin(dLambda / 2)
        let range = rNm * 2 * atan2(sqrt(a), sqrt(1 - a))

        return BearingRange(bearing: bearing, range: range)
    }

    /// Shortest signed delta between two bearings, e.g. 359 -> 2 gives +3.
    static func bearingDelta(from: Double, to: Double) -> Double {
        var d = (to - from).truncatingRemainder(dividingBy: 360)
        if d > 180 { d -= 360 }
        if d < -180 { d += 360 }
        return d
    }

    /// Zoom level whose ground scale at `lat` matches `rangeNm` across `pixels`,
    /// so the map's visible extent lines up with the radar's outer ring.
    static func zoomForRange(rangeNm: Double, lat: Double, pixels: Double) -> Double {
        let metersPerPixel = (rangeNm * 1852) / pixels
        return log2(156543.03392 * cos(lat * .pi / 180) / metersPerPixel)
    }

    /// Bounding box `rangeNm` around (lat, lon), for the runway Overpass query.
    static func rangeBBox(lat: Double, lon: Double, rangeNm: Double) -> (south: Double, west: Double, north: Double, east: Double) {
        let rangeM = rangeNm * 1852
        let latDelta = rangeM / 111320
        let lonDelta = rangeM / (111320 * cos(lat * .pi / 180))
        return (lat - latDelta, lon - lonDelta, lat + latDelta, lon + lonDelta)
    }
}
