import Foundation

struct Coordinate: Equatable {
    let lat: Double
    let lon: Double
}

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
    ///
    /// 156543.03392 is metres per pixel at zoom 0 for 256-pixel tiles; MapLibre
    /// counts zoom in 512-point tiles, so one level fewer is needed. The kiosk
    /// has always had the "- 1"; this copy didn't, and drew the map at twice
    /// the radar's scale -- Durham, 9 nm from RDU, showed at the 18 nm mark --
    /// which zooming and dragging made plain: the map slid twice as far as
    /// the finger.
    static func zoomForRange(rangeNm: Double, lat: Double, pixels: Double) -> Double {
        let metersPerPixel = (rangeNm * 1852) / pixels
        return log2(156543.03392 * cos(lat * .pi / 180) / metersPerPixel) - 1
    }

    /// The point `rangeNm` along `bearing` from `from`, on the great circle.
    static func destination(from c: Coordinate, bearing: Double, rangeNm: Double) -> Coordinate {
        let rNm = 3440.065
        let d = rangeNm / rNm, b = bearing * .pi / 180
        let phi1 = c.lat * .pi / 180, lam1 = c.lon * .pi / 180
        let phi2 = asin(sin(phi1) * cos(d) + cos(phi1) * sin(d) * cos(b))
        let lam2 = lam1 + atan2(sin(b) * sin(d) * cos(phi1), cos(d) - sin(phi1) * sin(phi2))
        return Coordinate(lat: phi2 * 180 / .pi, lon: (lam2 * 180 / .pi + 540).truncatingRemainder(dividingBy: 360) - 180)
    }

    /// Where `c` lies relative to `centre`, in nm east and north, on a flat
    /// map drawn at the centre's latitude: exact enough across one view,
    /// wherever in the world the view is (roadmap 2.23).
    static func localOffset(of c: Coordinate, from centre: Coordinate) -> (east: Double, north: Double) {
        var dLon = c.lon - centre.lon
        if dLon > 180 { dLon -= 360 } else if dLon < -180 { dLon += 360 }
        return (dLon * 60 * cos(centre.lat * .pi / 180), (c.lat - centre.lat) * 60)
    }

    /// The point `east` and `north` nm from `centre`, on that same flat map.
    static func moved(_ centre: Coordinate, east: Double, north: Double) -> Coordinate {
        let lat = max(-85, min(85, centre.lat + north / 60))
        var lon = centre.lon + east / (60 * cos(centre.lat * .pi / 180))
        if lon > 180 { lon -= 360 } else if lon < -180 { lon += 360 }
        return Coordinate(lat: lat, lon: lon)
    }

    /// Bounding box `rangeNm` around (lat, lon), for the runway Overpass query.
    static func rangeBBox(lat: Double, lon: Double, rangeNm: Double) -> (south: Double, west: Double, north: Double, east: Double) {
        let rangeM = rangeNm * 1852
        let latDelta = rangeM / 111320
        let lonDelta = rangeM / (111320 * cos(lat * .pi / 180))
        return (lat - latDelta, lon - lonDelta, lat + latDelta, lon + lonDelta)
    }
}
