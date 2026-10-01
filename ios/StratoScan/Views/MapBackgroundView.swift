import SwiftUI
import MapLibre
import CoreLocation

/// Non-interactive background map, mirroring the web version's #mapbg +
/// initMap()/recolorLabels()/loadRunways(): "liberty" style (the "dark"
/// OpenFreeMap style turned out to be near-grayscale by design), place
/// labels flipped to light-text/dark-halo, and a runway GeoJSON layer
/// sourced from Overpass once `runwayGeoJSON` arrives.
///
/// Darkening (the equivalent of #mapbg's CSS `filter: brightness()
/// saturate()`) is deliberately NOT done here — MLNMapView is Metal-backed,
/// and a CALayer.filters approach didn't visibly apply. It's applied where
/// this view is used instead, via SwiftUI's own .saturation()/.brightness()
/// modifiers, which work reliably regardless of the wrapped view's
/// rendering technology.
struct MapBackgroundView: UIViewRepresentable {
    let center: Coordinate
    let zoom: Double
    let runwayGeoJSON: Data?
    /// The theme: its place-name colours (dark-on-light for Daylight).
    var palette: Palette = .classic
    /// Weather (#42), as on the radar's screen: precipitation radar from
    /// RainViewer (on by default), satellite lightning from RealEarth (off by
    /// default, and only where it covers -- the Americas).
    var showStorms = true
    var showLightning = false

    private static let styleURL = URL(string: "https://tiles.openfreemap.org/styles/liberty")!

    func makeUIView(context: Context) -> MLNMapView {
        let map = MLNMapView(frame: .zero, styleURL: Self.styleURL)
        map.setCenter(CLLocationCoordinate2D(latitude: center.lat, longitude: center.lon), zoomLevel: zoom, animated: false)
        map.isUserInteractionEnabled = false
        map.logoView.isHidden = true
        map.attributionButton.isHidden = false
        map.delegate = context.coordinator
        context.coordinator.map = map
        context.coordinator.setPalette(palette)
        return map
    }

    func updateUIView(_ uiView: MLNMapView, context: Context) {
        context.coordinator.setPalette(palette)
        context.coordinator.setWeather(storms: showStorms, lightning: showLightning, at: center)
        uiView.setCenter(CLLocationCoordinate2D(latitude: center.lat, longitude: center.lon), zoomLevel: zoom, animated: false)
        context.coordinator.pendingRunwayGeoJSON = runwayGeoJSON
        context.coordinator.addRunwaysIfReady()
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, MLNMapViewDelegate {
        weak var map: MLNMapView?
        var pendingRunwayGeoJSON: Data?
        private var runwaysAdded = false
        private var styleLoaded = false

        private var palette: Palette = .classic

        func setPalette(_ p: Palette) {
            guard p != palette else { return }
            palette = p
            if styleLoaded, let style = map?.style { recolorLabels(style) }
        }

        // ---- weather (#42): the kiosk's refreshStorms/refreshLightning -------
        private static let rainViewerAPI = URL(string: "https://api.rainviewer.com/public/weather-maps.json")!
        private static let lightningTiles = "https://realearth.ssec.wisc.edu/tiles/GOESEastGLMFEDRadC/{z}/{x}/{y}.png"
        private var storms = true, lightning = false, centre: Coordinate?
        private var stormURL: String?
        private var stormsCheckedAt = Date.distantPast
        private var lightningAt = Date.distantPast

        func setWeather(storms: Bool, lightning: Bool, at centre: Coordinate) {
            self.storms = storms
            self.lightning = lightning
            self.centre = centre
            applyWeather()
        }

        /// Called on every update; does work only when something is due.
        private func applyWeather() {
            guard styleLoaded, let style = map?.style else { return }
            if storms {
                if Date().timeIntervalSince(stormsCheckedAt) > 5 * 60 {   // RainViewer's own cadence
                    stormsCheckedAt = Date()
                    Task { await refreshStorms() }
                }
            } else {
                remove("storms", from: style)
                stormURL = nil
                stormsCheckedAt = .distantPast
            }
            if lightning, let c = centre, (-135.0 ... -15.0).contains(c.lon), (-60.0 ... 60.0).contains(c.lat) {
                if style.layer(withIdentifier: "lightning") == nil || Date().timeIntervalSince(lightningAt) > 2 * 60 {
                    lightningAt = Date()
                    // a fresh query string, or the tiles stay cached
                    addRaster("lightning", url: Self.lightningTiles + "?t=\(Int(Date().timeIntervalSince1970))", opacity: 0.85, to: style)
                }
            } else {
                remove("lightning", from: style)
                lightningAt = .distantPast
            }
        }

        private func refreshStorms() async {
            struct Maps: Decodable {
                struct Frame: Decodable { let path: String }
                struct Radar: Decodable { let past: [Frame] }
                let host: String
                let radar: Radar
            }
            guard let (data, _) = try? await URLSession.shared.data(from: Self.rainViewerAPI),
                  let maps = try? JSONDecoder().decode(Maps.self, from: data),
                  let latest = maps.radar.past.last else { return }
            // colour scheme 6 (NEXRAD's green-yellow-red), smoothed, snow shown
            let url = "\(maps.host)\(latest.path)/256/{z}/{x}/{y}/6/1_1.png"
            await MainActor.run {
                guard self.storms, url != self.stormURL, let style = self.map?.style else { return }
                self.stormURL = url
                self.addRaster("storms", url: url, opacity: 0.65, to: style)
            }
        }

        private func addRaster(_ id: String, url: String, opacity: Double, to style: MLNStyle) {
            remove(id, from: style)
            let source = MLNRasterTileSource(identifier: id, tileURLTemplates: [url],
                                             options: [.tileSize: 256, .maximumZoomLevel: 7])
            style.addSource(source)
            let layer = MLNRasterStyleLayer(identifier: id, source: source)
            layer.rasterOpacity = NSExpression(forConstantValue: opacity)
            style.addLayer(layer)
        }

        private func remove(_ id: String, from style: MLNStyle) {
            if let l = style.layer(withIdentifier: id) { style.removeLayer(l) }
            if let s = style.source(withIdentifier: id) { style.removeSource(s) }
        }

        func mapView(_ mapView: MLNMapView, didFinishLoading style: MLNStyle) {
            styleLoaded = true
            recolorLabels(style)
            applyWeather()
            addRunwaysIfReady()
        }

        /// "liberty" is styled for a light background (black text, white
        /// halo). On the darkened maps place names flip to light-on-dark so
        /// they stay legible; Daylight keeps them dark-on-light (the kiosk's
        /// recolorLabels, per theme).
        private func recolorLabels(_ style: MLNStyle) {
            let labelLayerIDs = ["label_city_capital", "label_city", "label_town", "label_village", "label_other"]
            for id in labelLayerIDs {
                guard let layer = style.layer(withIdentifier: id) as? MLNSymbolStyleLayer else { continue }
                layer.textColor = NSExpression(forConstantValue: UIColor(palette.mapLabel))
                layer.textHaloColor = NSExpression(forConstantValue: UIColor(palette.mapHalo))
            }
            if let water = style.layer(withIdentifier: "water_name_point_label") as? MLNSymbolStyleLayer {
                water.textColor = NSExpression(forConstantValue: UIColor(palette.mapWater))
                water.textHaloColor = NSExpression(forConstantValue: UIColor(palette.mapHalo))
            }
        }

        func addRunwaysIfReady() {
            guard styleLoaded, !runwaysAdded, let data = pendingRunwayGeoJSON, let map, let style = map.style else { return }
            guard let shape = try? MLNShape(data: data, encoding: String.Encoding.utf8.rawValue) else { return }
            let source = MLNShapeSource(identifier: "runways", shape: shape, options: nil)
            style.addSource(source)

            let taxiway = MLNLineStyleLayer(identifier: "runways-taxiway", source: source)
            taxiway.predicate = NSPredicate(format: "aeroway == %@", "taxiway")
            taxiway.lineColor = NSExpression(forConstantValue: UIColor(Color(hex: "#5a6469")))
            taxiway.lineWidth = NSExpression(forConstantValue: 1.2)
            style.addLayer(taxiway)

            let runway = MLNLineStyleLayer(identifier: "runways-runway", source: source)
            runway.predicate = NSPredicate(format: "aeroway == %@", "runway")
            runway.lineColor = NSExpression(forConstantValue: UIColor(Color(hex: "#c7d0d3")))
            runway.lineWidth = NSExpression(forConstantValue: 2.5)
            style.addLayer(runway)

            runwaysAdded = true
        }
    }
}
