import SwiftUI
import MapLibre
import CoreLocation
import CoreImage

/// Non-interactive background map, mirroring the web version's #mapbg +
/// initMap()/recolorLabels()/loadRunways(): "liberty" style (the "dark"
/// OpenFreeMap style turned out to be near-grayscale by design), darkened
/// via a CALayer filter instead of MapLibre GL JS's CSS filter equivalent,
/// place labels flipped to light-text/dark-halo, and a runway GeoJSON
/// layer sourced from Overpass once `runwayGeoJSON` arrives.
struct MapBackgroundView: UIViewRepresentable {
    let center: Coordinate
    let zoom: Double
    let runwayGeoJSON: Data?

    private static let styleURL = URL(string: "https://tiles.openfreemap.org/styles/liberty")!

    func makeUIView(context: Context) -> MLNMapView {
        let map = MLNMapView(frame: .zero, styleURL: Self.styleURL)
        map.setCenter(CLLocationCoordinate2D(latitude: center.lat, longitude: center.lon), zoomLevel: zoom, animated: false)
        map.isUserInteractionEnabled = false
        map.logoView.isHidden = true
        map.attributionButton.isHidden = false
        map.delegate = context.coordinator
        context.coordinator.map = map
        applyDarkeningFilter(to: map)
        return map
    }

    func updateUIView(_ uiView: MLNMapView, context: Context) {
        uiView.setCenter(CLLocationCoordinate2D(latitude: center.lat, longitude: center.lon), zoomLevel: zoom, animated: false)
        context.coordinator.pendingRunwayGeoJSON = runwayGeoJSON
        context.coordinator.addRunwaysIfReady()
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    /// MapLibre Native (unlike the web SDK) has no CSS filter equivalent,
    /// so darkening/saturating the whole map happens via a CALayer filter
    /// on the map's own layer — same net visual effect as #mapbg's
    /// `filter: brightness(0.36) saturate(1.5)` on the web version.
    private func applyDarkeningFilter(to map: MLNMapView) {
        guard let filter = CIFilter(name: "CIColorControls") else { return }
        filter.setValue(0.36, forKey: kCIInputBrightnessKey) // matches web #mapbg filter value
        filter.setValue(1.5, forKey: kCIInputSaturationKey)
        map.layer.filters = [filter]
    }

    final class Coordinator: NSObject, MLNMapViewDelegate {
        weak var map: MLNMapView?
        var pendingRunwayGeoJSON: Data?
        private var runwaysAdded = false
        private var styleLoaded = false

        func mapView(_ mapView: MLNMapView, didFinishLoading style: MLNStyle) {
            styleLoaded = true
            recolorLabels(style)
            addRunwaysIfReady()
        }

        /// "liberty" is styled for a light background (black text, white
        /// halo) — flip place-name labels to the opposite convention so
        /// they stay legible once the CALayer filter darkens everything.
        private func recolorLabels(_ style: MLNStyle) {
            let labelLayerIDs = ["label_city_capital", "label_city", "label_town", "label_village", "label_other"]
            for id in labelLayerIDs {
                guard let layer = style.layer(withIdentifier: id) as? MLNSymbolStyleLayer else { continue }
                layer.textColor = NSExpression(forConstantValue: UIColor(Color(hex: "#e8e2d5")))
                layer.textHaloColor = NSExpression(forConstantValue: UIColor(Color(hex: "#05080a")))
            }
            if let water = style.layer(withIdentifier: "water_name_point_label") as? MLNSymbolStyleLayer {
                water.textColor = NSExpression(forConstantValue: UIColor(Color(hex: "#9fc4e8")))
                water.textHaloColor = NSExpression(forConstantValue: UIColor(Color(hex: "#05080a")))
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
