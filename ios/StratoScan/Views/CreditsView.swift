import SwiftUI

/// About & credits: required attributions and licences for what the app
/// uses (see THIRD_PARTY_NOTICES.md in the repository).
struct CreditsView: View {
    private var version: String {
        let v = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?"
        let b = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?"
        return "\(v) (\(b))"
    }

    var body: some View {
        List {
            Section {
                Text("StratoScan shows the aircraft your own StratoScan radar hears, and sends you its alerts.")
                LabeledContent("Version", value: version)
                Link("Source code (MIT licence)", destination: URL(string: "https://github.com/mferris/StratoScan")!)
            } footer: {
                Text("StratoScan™ and the StratoScan logo are trademarks of Michael Ferris. © 2026 Michael Ferris.")
            }

            Section("Map") {
                credit("Map data © OpenStreetMap contributors",
                       "Available under the Open Database Licence.", "https://www.openstreetmap.org/copyright")
                credit("Map style and tiles: OpenFreeMap © OpenMapTiles",
                       nil, "https://openfreemap.org/")
                credit("Runways: OpenStreetMap data via the Overpass API",
                       "© OpenStreetMap contributors, ODbL.", "https://overpass-api.de/")
                credit("Weather radar: RainViewer",
                       nil, "https://www.rainviewer.com/")
                credit("Lightning: SSEC RealEarth, University of Wisconsin–Madison",
                       "GOES-East Geostationary Lightning Mapper.", "https://realearth.ssec.wisc.edu/")
            }

            Section("Aircraft") {
                credit("Photos from planespotters.net",
                       "Each photo is credited to its photographer where it is shown.", "https://www.planespotters.net/")
                credit("Routes from the adsb.im route API", nil, "https://adsb.im/")
                credit("Aircraft types from the tar1090 aircraft database, read from your radar",
                       nil, "https://github.com/wiedehopf/tar1090-db")
                credit("Aircraft your radar didn't hear: network data © ADSB.lol contributors",
                       "Available under the Open Database Licence.", "https://www.adsb.lol/")
                credit("Registered owners of private aircraft from adsbdb",
                       nil, "https://www.adsbdb.com/")
            }

            Section {
                Text(Self.mapLibreLicence)
                    .font(.system(.caption2, design: .monospaced))
                    .textSelection(.enabled)
            } header: {
                Text("MapLibre Native")
            }
        }
        .navigationTitle("About & credits")
    }

    private func credit(_ title: String, _ detail: String?, _ url: String) -> some View {
        Link(destination: URL(string: url)!) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title).foregroundColor(.primary)
                if let detail { Text(detail).font(.caption).foregroundColor(.secondary) }
            }
        }
    }

    // Verbatim from MapLibre Native's LICENSE.md (BSD 2-Clause), which
    // requires this notice in a binary distribution's materials.
    static let mapLibreLicence = """
    BSD 2-Clause License

    Copyright (c) 2021 MapLibre contributors

    Copyright (c) 2018-2021 MapTiler.com

    Copyright (c) 2014-2020 Mapbox

    Redistribution and use in source and binary forms, with or without \
    modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice, \
    this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice, \
    this list of conditions and the following disclaimer in the documentation \
    and/or other materials provided with the distribution.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" \
    AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE \
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE \
    ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE \
    LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR \
    CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF \
    SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS \
    INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN \
    CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) \
    ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE \
    POSSIBILITY OF SUCH DAMAGE.
    """
}
