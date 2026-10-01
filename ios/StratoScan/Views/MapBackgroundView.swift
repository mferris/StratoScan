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

        func mapView(_ mapView: MLNMapView, didFinishLoading style: MLNStyle) {
            styleLoaded = true
            recolorLabels(style)
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
