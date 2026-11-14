#!/usr/bin/env python3
"""The app on the iPhone Duo, folded and unfolded (#101).

The iPhone Duo's screens are wider than any other iPhone's (466 x 678 pt
folded, 669 x 951 unfolded), its inner display turns with the phone although
the app is portrait-only, and folding or unfolding changes the layout under
whatever is open. So:

- Sky view's lens scale (SkyLens) fits the camera's picture to whichever side
  of the screen it fills, so labels land where the aircraft are on every
  screen shape, either way round, and is unchanged on ordinary iPhones;
- Sky view's motion and the Compass's heading are measured from their own
  screen on iOS 27 (deviceMotionBody, headingBody), and let go on closing;
- the camera picture turns to stay upright, and the projection uses the
  whole screen, as the picture does;
- an aircraft's details, and a Compass open over them, survive the change
  between the sheet (folded) and the side panel (unfolded);
- Sky view's controls stay inside the safe area, so Close is never under
  the camera or the status icons (the Duo's outer screen hid it);
- Settings stays one column.

The first part reads the app's Swift. Where swiftc is installed the second
compiles SkyLens and checks its numbers.

Run: python3 tests/test_app_sky_lens.py
"""
import math
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
VIEWS = ROOT / "ios" / "StratoScan" / "Views"
fails = 0


def check(ok, what):
    global fails
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails += 1


def code(path):
    """The Swift without its comments."""
    return "\n".join(re.sub(r"(?<![:\"])//.*$", "", line) for line in path.read_text().splitlines())


sky = code(VIEWS / "SkyView.swift")
compass = code(VIEWS / "CompassView.swift")
content = code(VIEWS / "ContentView.swift")
details = code(VIEWS / "AircraftDetailView.swift")
settings = code(VIEWS / "SettingsView.swift")
location = code(ROOT / "ios" / "StratoScan" / "Location" / "PhoneLocation.swift")
model = code(ROOT / "ios" / "StratoScan" / "ViewModels" / "RadarViewModel.swift")

# ---- the wiring -----------------------------------------------------------------------
check(sky.count("SkyLens.focalLength(size: size, longFovDegrees: camera.fieldOfView)") == 2
      and "tan(camera.fieldOfView" not in sky,
      "both Sky view projections (labels, tracks) use the lens scale, not the screen's height alone")
check("BodyAnchor { motion.measure(from: $0) }" in sky and "manager.deviceMotionBody = view" in sky
      and "manager.deviceMotionBody = nil" in sky,
      "Sky view's motion is measured from its own screen, and lets the view go on closing")
check("transposed = nil" in sky.split("func measure(from")[1].split("private func update")[0],
      "a new body settles the matrix's direction again")
check("BodyAnchor { location.measureHeading(from: $0) }" in compass
      and "manager.headingBody = view" in location and "manager.headingBody = nil" in location,
      "the Compass's heading is measured from its own screen, and lets the view go on stopping")
check(all(s.count("#available(iOS 27.0, *)") >= 2 for s in (sky, location)),
      "the iOS 27 measuring is guarded for the phones on iOS 17 to 26")
check("AVCaptureDevice.RotationCoordinator(device: device, previewLayer: preview)" in sky
      and "videoRotationAngleForHorizonLevelPreview" in sky and ".initial" in sky
      and "connection.videoRotationAngle = angle" in sky and "UIInterfaceOrientation" not in sky,
      "the camera picture turns with the screen by Apple's coordinator, half turns too, not a hand-made table")
check("CameraPreview(session: camera.session, device: camera.device)" in sky and "self.device = cam" in sky,
      "the coordinator starts once the camera is in the session, when the preview has its connection")
body = sky.split("var body: some View {")[1].split(".onAppear")[0]
scene, _, controls = body.partition(".overlay {")
controls, _, panel = controls.partition(".overlay {")
check(scene.rstrip().endswith(".ignoresSafeArea()") and body.count(".ignoresSafeArea()") == 2,
      "the projection's size and middle are the whole screen's, as the picture and labels are")
check('accessibilityLabel("Close Sky view")' in controls and "Back to the radar" in controls
      and "Close Sky view" not in scene and "gnoringSafeArea" not in controls and "gnoresSafeArea" not in controls
      and all(int(n) <= 8 for n in re.findall(r"\.padding\(\.top, (\d+)\)", controls)),
      "Sky view's Close and Back sit inside the safe area, clear of the Duo's camera and status icons")
check(".clearOfScreenCorners()" in controls,
      "and come in from the screen's rounded corners where nothing sits across the top (the Duo unfolded)")
check('controlLabel("Close", systemImage: "xmark")' in controls and ".fixedSize()" in controls
      and "xmark.circle.fill" not in controls,
      "Close is a word on a dark capsule, never squeezed, not a small bare cross")
check("sidewaysPanel(d, in: geo.size)" in panel and "sidewaysPanel" not in scene + controls
      and ".ignoresSafeArea()" in panel,
      "the sideways details panel still covers the controls, at the whole screen's size")
m = re.search(r"\.padding\(\.bottom, (\d+)\)", controls)
check(m is not None and int(m.group(1)) >= 14 + 26 + 4, "the prompts end above Sky view's logo")
corner = content.split("struct ClearOfScreenCorners")[1]
check("guard i.top < bare else { return EdgeInsets() }" in corner and "static let bare: CGFloat = 20" in corner
      and "max(0, side - i.leading)" in corner and "max(0, side - i.trailing)" in corner
      and "ignoresSafeArea" not in corner,
      "the corner margin is only added where the top is bare, and only what the safe area doesn't give")
check(content.count(".clearOfScreenCorners()") == 3
      and "hud(geo.size.width - corners.leading - corners.trailing)" in content,
      "the radar's top bar, the wall mode's way out and the logo's column all keep off the corners")
check("3 * 44 + 2 * Self.barSpacing" in content and "HStack(spacing: ContentView.barSpacing)" in content,
      "the logo is fitted to the room the buttons and the gaps between them leave")
check("if sel == nil && (viewModel.detailsInPanel || showSky) { return }" in content
      and "viewModel.detailsInPanel = isPad" in content,
      "unfolding with details open moves them to the side panel instead of closing them")
check("inPanel: true" in content and "inPanel: false" in content
      and "if let inPanel, inPanel != viewModel.detailsInPanel { return }" in details
      and "@Published var compass: CompassOpen?" in model and "showCompass" not in details,
      "a Compass open over the details reopens over them after a fold")
check("onRadar: inPanel != nil" in details and "viewModel.compass?.onRadar == false" in sky,
      "a Compass opened in Sky view is Sky view's alone: the side panel under it doesn't open one too")
check("isPad || showSky ? nil" in content, "the details sheet waits while Sky view covers the radar")
check(".environment(\\.colorScheme, .dark)" in details.split("CompassView(")[1][:300],
      "the Compass reads light on dark over the side panel too")
check(".navigationViewStyle(.stack)" in settings, "Settings stays one column on a wide screen")

# ---- the numbers ----------------------------------------------------------------------
swiftc = shutil.which("swiftc") or (subprocess.run(["xcrun", "--find", "swiftc"], capture_output=True, text=True).stdout.strip()
                                    if shutil.which("xcrun") else "")
if not swiftc or platform.system() != "Darwin":
    print("skip the compiled checks: no swiftc here (they run on the Mac that builds the app)")
else:
    FOV = 65.0
    SIZES = [(393, 852), (440, 956), (466, 678), (669, 951), (951, 669), (820, 1180), (300, 300), (0, 0)]
    main = "import CoreGraphics\n" + "".join(
        f'print(SkyLens.focalLength(size: CGSize(width: {w}, height: {h}), longFovDegrees: {FOV}))\n' for w, h in SIZES)
    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        (t / "main.swift").write_text(main)
        exe = t / "lens"
        build = subprocess.run([swiftc, "-O", str(VIEWS / "SkyLens.swift"), str(t / "main.swift"), "-o", str(exe)],
                               capture_output=True, text=True)
        check(build.returncode == 0, "SkyLens compiles on its own" + ("" if build.returncode == 0 else ": " + build.stderr[-400:]))
        if build.returncode == 0:
            got = dict(zip(SIZES, (float(x) for x in subprocess.run([str(exe)], capture_output=True, text=True).stdout.split())))
            tl = math.tan(math.radians(FOV / 2))
            old = lambda w, h: (max(w, h) / 2) / tl   # what Sky view assumed before
            for size in [(393, 852), (440, 956)]:
                check(abs(got[size] - old(*size)) < 1e-6, f"an ordinary iPhone ({size[0]} x {size[1]}) is unchanged")
            for size in [(466, 678), (669, 951)]:
                want = (min(size) / 2) / (tl / (16 / 9))
                check(abs(got[size] - want) < 1e-6 and got[size] > old(*size) * 1.15,
                      f"the Duo's {size[0]} x {size[1]} screen fits the picture's short side (labels about 20% further out)")
            check(abs(got[(951, 669)] - got[(669, 951)]) < 1e-9, "a sideways screen scales the same")
            check(got[(0, 0)] == 0, "an empty screen gives no scale rather than a crash")

sys.exit(1 if fails else 0)
