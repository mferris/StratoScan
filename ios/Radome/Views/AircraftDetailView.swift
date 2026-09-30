import SwiftUI

/// Details for one aircraft, opened by tapping it on the radar. Refreshes
/// every second from the live plane state, like the kiosk's detail panel.
struct AircraftDetailView: View {
    @ObservedObject var viewModel: RadarViewModel
    let hex: String
    @State private var photo: Photo?
    @Environment(\.dismiss) private var dismiss

    struct Photo: Decodable {
        let found: Bool
        let thumb: String?
        let thumbLarge: String?
        let photographer: String?
        let link: String?
    }

    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { _ in
            let p = viewModel.planes[hex]
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    header(p)
                    if p != nil {
                        // Keep this aircraft in the middle of the radar and map,
                        // zoomed in, to see exactly where it is (roadmap 2.9).
                        Button(viewModel.followHex == hex ? "Stop following" : "Follow on the radar") {
                            if viewModel.followHex == hex {
                                viewModel.followHex = nil
                            } else {
                                viewModel.followHex = hex
                                if viewModel.rangeNm > 5 { viewModel.setRange(5) }
                                dismiss()
                            }
                        }
                        .buttonStyle(.bordered)
                    }
                    photoView
                    if let p {
                        grid(p)
                    } else {
                        Text("Out of range now.").foregroundColor(.secondary)
                    }
                    Text("ICAO \(hex.uppercased())")
                        .font(.system(.caption, design: .monospaced)).foregroundColor(.secondary)
                }
                .padding(20)
            }
        }
        .task(id: hex) { await loadPhoto() }
    }

    private func header(_ p: PlaneState?) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(p?.cs ?? hex.uppercased())
                .font(.system(size: 28, weight: .semibold, design: .monospaced))
            if let p {
                Text(p.airlineLabel).foregroundColor(p.badgeColor)
                if let type = p.typeLabel { Text(type).foregroundColor(.secondary) }
                if let r = p.feedRoute {
                    Text(r.plausible == false ? "\(r.text) (unconfirmed)" : r.text).font(.callout)
                } else if let r = viewModel.routeClient.cache[p.cs], let route = r {
                    Text("\(route.from) → \(route.to)").font(.callout)
                }
                if let o = p.owner {
                    Text("Registered to \(o.name)\(o.country.map { " (\($0))" } ?? "")")
                        .font(.caption).foregroundColor(.secondary)
                }
                if p.isNetwork {
                    // Said plainly: this came from the network, not the antenna.
                    // adsb.lol's data is ODbL, which asks for this credit.
                    Text("Reported by adsb.lol, not heard by this radar. Network data © ADSB.lol contributors (ODbL).")
                        .font(.caption).foregroundColor(.orange)
                }
            }
        }
    }

    @ViewBuilder private var photoView: some View {
        if let photo, photo.found, let s = photo.thumbLarge ?? photo.thumb, let url = URL(string: s) {
            VStack(alignment: .leading, spacing: 4) {
                AsyncImage(url: url) { img in
                    img.resizable().scaledToFit()
                } placeholder: {
                    Color.gray.opacity(0.15).frame(height: 180)
                }
                .clipShape(RoundedRectangle(cornerRadius: 8))
                // planespotters.net requires the credit and a link back.
                if let link = photo.link.flatMap(URL.init(string:)) {
                    Link("© \(photo.photographer ?? "Unknown") · planespotters.net", destination: link)
                        .font(.caption)
                } else {
                    Text("© \(photo.photographer ?? "Unknown") · planespotters.net").font(.caption)
                }
            }
        }
    }

    private func grid(_ p: PlaneState) -> some View {
        let rows: [(String, String)] = [
            ("Altitude", altitude(p.alt)),
            ("Speed", p.speed.map { "\(Int($0.rounded())) kt" } ?? "—"),
            ("Heading", "\(Int(p.hdg.rounded()) % 360)°"),
            ("Distance", String(format: "%.1f nm %@", p.targetRange, compass(p.targetBearing))),
        ]
        return VStack(spacing: 10) {
            ForEach(rows, id: \.0) { row in
                HStack {
                    Text(row.0).foregroundColor(.secondary)
                    Spacer()
                    Text(row.1).font(.system(.body, design: .monospaced))
                }
            }
        }
    }

    private func altitude(_ a: Altitude) -> String {
        switch a {
        case .ground: return "On the ground"
        case .unknown: return "—"
        case .feet(let ft): return "\(Int(ft).formatted()) ft"
        }
    }

    private func compass(_ bearing: Double) -> String {
        let points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return points[Int(((bearing.truncatingRemainder(dividingBy: 360) + 360).truncatingRemainder(dividingBy: 360) / 45).rounded()) % 8]
    }

    /// The radar's own photo service (deploy/photo-proxy.py), which caches
    /// planespotters.net lookups so every viewer shares one request.
    private func loadPhoto() async {
        guard let (data, _) = try? await URLSession.shared.data(from: APIConfig.url("/photo/\(hex)")) else { return }
        photo = try? JSONDecoder().decode(Photo.self, from: data)
    }
}
