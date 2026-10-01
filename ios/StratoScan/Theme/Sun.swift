import Foundation

/// Where the sun is, for wall mode's night dimming (#39): the kiosk dims
/// between sunset and sunrise at the radar, and so does an iPad on the wall.
enum Sun {
    /// The sun's elevation above the horizon, in degrees, at a place and time
    /// (the low-precision formula from the Astronomical Almanac; well within
    /// a minute of sunset, which is all dimming needs).
    static func elevation(lat: Double, lon: Double, at date: Date = Date()) -> Double {
        let n = date.timeIntervalSince1970 / 86400 + 2440587.5 - 2451545.0   // days since J2000
        let rad = Double.pi / 180
        let meanLon = (280.460 + 0.9856474 * n).truncatingRemainder(dividingBy: 360)
        let anomaly = (357.528 + 0.9856003 * n).truncatingRemainder(dividingBy: 360) * rad
        let eclipticLon = (meanLon + 1.915 * sin(anomaly) + 0.020 * sin(2 * anomaly)) * rad
        let obliquity = (23.439 - 0.0000004 * n) * rad
        let declination = asin(sin(obliquity) * sin(eclipticLon))
        let rightAscension = atan2(cos(obliquity) * sin(eclipticLon), cos(eclipticLon))
        let gmstHours = (18.697374558 + 24.06570982441908 * n).truncatingRemainder(dividingBy: 24)
        let hourAngle = (gmstHours * 15 + lon) * rad - rightAscension
        let phi = lat * rad
        return asin(sin(phi) * sin(declination) + cos(phi) * cos(declination) * cos(hourAngle)) / rad
    }

    /// Between sunset and sunrise: the sun's upper edge below the horizon,
    /// refraction allowed for (-0.833°), as sunset is usually defined.
    static func isNight(lat: Double, lon: Double, at date: Date = Date()) -> Bool {
        elevation(lat: lat, lon: lon, at: date) < -0.833
    }
}
