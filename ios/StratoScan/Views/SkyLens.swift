import CoreGraphics
import Foundation

/// How far from the middle of the screen a direction lands in Sky view: the
/// camera's focal length in points (#101).
///
/// The camera's picture is 16:9 (`sessionPreset = .high`) and fills the screen
/// (aspect-fill), so whichever side of the screen the picture fits exactly
/// sets the scale, and the other side is cropped. On an ordinary iPhone the
/// screen is narrower than 9:16, so its long side spans the camera's full
/// long-side field of view, which is all this used to assume. The iPhone
/// Duo's screens are wider than that (466 x 678 pt folded, 669 x 951
/// unfolded), so there the short side fits and the long side is cropped:
/// assuming the long side put every label about 20% too near the middle.
/// Taking the larger of the two scales is right for every shape, either way
/// round, so a sideways screen needs nothing more.
///
/// Pure arithmetic, so tests/test_app_sky_lens.py compiles and checks it.
enum SkyLens {
    /// - Parameters:
    ///   - size: the view the picture fills, in points.
    ///   - longFovDegrees: the camera's field of view across its long side
    ///     (`AVCaptureDevice.Format.videoFieldOfView`).
    ///   - pictureAspect: the picture's long side over its short side.
    static func focalLength(size: CGSize, longFovDegrees: Double, pictureAspect: Double = 16.0 / 9.0) -> CGFloat {
        let long = Double(max(size.width, size.height))
        let short = Double(min(size.width, size.height))
        guard long > 0, longFovDegrees > 0, pictureAspect > 0 else { return 0 }
        let tanLong = tan(longFovDegrees * .pi / 360)
        let tanShort = tanLong / pictureAspect
        return CGFloat(max((long / 2) / tanLong, (short / 2) / tanShort))
    }
}
