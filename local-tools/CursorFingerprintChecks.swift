import AppKit
import Darwin

@main
struct CursorFingerprintChecks {
    static var checks = 0

    static func expect(_ value: @autoclosure () -> Bool, _ message: String) {
        if !value() {
            FileHandle.standardError.write(Data("FAIL after \(checks) checks: \(message)\n".utf8))
            exit(1)
        }
        checks += 1
    }

    static func bitmap(_ pixels: Int = 24) -> NSBitmapImageRep {
        let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pixels,
                                  pixelsHigh: pixels, bitsPerSample: 8,
                                  samplesPerPixel: 4, hasAlpha: true,
                                  isPlanar: false, colorSpaceName: .calibratedRGB,
                                  bytesPerRow: 0, bitsPerPixel: 0)!
        memset(rep.bitmapData!, 0, rep.bytesPerPlane)
        for y in 0..<pixels {
            for x in 0..<pixels {
                let pixel = rep.bitmapData!.advanced(by: y * rep.bytesPerRow + x * 4)
                pixel[0] = 255
                pixel[3] = 255
            }
        }
        return rep
    }

    static func fingerprint(_ image: NSImage, hotSpot: NSPoint = .zero,
                            display: NSSize = NSSize(width: 820, height: 1180)) -> Int? {
        CursorImageFingerprint.make(image: image, hotSpot: hotSpot, displaySize: display)
    }

    static func cpuSeconds() -> Double {
        var time = timespec()
        clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &time)
        return Double(time.tv_sec) + Double(time.tv_nsec) / 1_000_000_000
    }

    static func main() {
        let rep = bitmap()
        let image = NSImage(size: NSSize(width: 24, height: 24))
        image.addRepresentation(rep)
        let initial = fingerprint(image)
        expect(initial != nil, "bitmap must have a fast fingerprint")
        expect(initial == fingerprint(image), "unchanged pixels must be stable")
        let originalTIFF = image.tiffRepresentation!
        let changedPixel = rep.bitmapData!.advanced(by: 4 * rep.bytesPerRow + 3 * 4)
        changedPixel[0] = 0
        changedPixel[2] = 255
        expect(initial != fingerprint(image), "in-place pixel mutation must be detected")
        changedPixel[0] = 255
        changedPixel[2] = 0
        expect(initial == fingerprint(image), "restored pixels must match")
        expect(originalTIFF == image.tiffRepresentation!, "fast path must not mutate the source image")
        expect(initial != fingerprint(image, hotSpot: NSPoint(x: 1, y: 2)), "hotspot must participate")
        expect(initial != fingerprint(image, display: NSSize(width: 1640, height: 2360)), "display scale must participate")
        expect(initial != fingerprint(image, display: NSSize(width: 820, height: 2360)), "display height must participate")
        image.size = NSSize(width: 12, height: 12)
        expect(initial != fingerprint(image), "logical image size must participate")
        image.size = NSSize(width: 24, height: 24)
        let retina = bitmap(48)
        retina.size = NSSize(width: 24, height: 24)
        image.addRepresentation(retina)
        let multi = fingerprint(image)
        expect(multi != initial, "all Retina representations must participate")
        retina.bitmapData![4 * retina.bytesPerRow + 3 * 4 + 1] = 255
        expect(multi != fingerprint(image), "Retina pixel mutation must be detected")
        let empty = NSImage(size: .zero)
        expect(fingerprint(empty) == nil, "empty image must fall back")
        let drawn = NSImage(size: NSSize(width: 24, height: 24), flipped: false) { rect in
            NSColor.red.setFill()
            rect.fill()
            return true
        }
        expect(fingerprint(drawn) == nil, "non-bitmap image must retain the legacy path")

        // The existing serialization and PNG conversion remain byte-for-byte
        // the same; the optimization only skips them for unchanged bitmaps.
        let before = image.tiffRepresentation!
        for _ in 0..<100 { _ = fingerprint(image) }
        expect(before == image.tiffRepresentation!, "fingerprinting must preserve serialized pixels")

        // Measure the unchanged-cursor hot path using CPU time so scheduling
        // delays and the current swap load do not dominate the comparison.
        let benchmarkImage = NSCursor.pointingHand.image
        let target = fingerprint(benchmarkImage) != nil ? benchmarkImage : image
        for _ in 0..<20 { _ = target.tiffRepresentation; _ = fingerprint(target) }
        let count = 500
        let oldStart = cpuSeconds()
        var oldHash = 0
        for _ in 0..<count { autoreleasepool { oldHash ^= target.tiffRepresentation!.hashValue } }
        let oldTime = cpuSeconds() - oldStart
        let newStart = cpuSeconds()
        var newHash = 0
        for _ in 0..<count { autoreleasepool { newHash ^= fingerprint(target)! } }
        let newTime = cpuSeconds() - newStart
        print("checks=\(checks) iterations=\(count) legacy_cpu_ms=\(oldTime * 1000) fast_cpu_ms=\(newTime * 1000) speedup=\(oldTime / max(newTime, 0.000001)) guard=\(oldHash ^ newHash)")
    }
}
