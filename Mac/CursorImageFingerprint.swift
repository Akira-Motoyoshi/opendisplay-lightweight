import AppKit

/// Read bitmap pixels directly before paying for TIFF serialization. In
/// particular, do not cache by NSImage identity: a cursor can mutate the
/// pixels of an existing representation while its objects stay the same.
enum CursorImageFingerprint {
    static func make(image: NSImage, hotSpot: NSPoint, displaySize: NSSize) -> Int? {
        let representations = image.representations
        guard !representations.isEmpty else { return nil }

        var hasher = Hasher()
        hasher.combine(image.size.width)
        hasher.combine(image.size.height)
        hasher.combine(hotSpot.x)
        hasher.combine(hotSpot.y)
        hasher.combine(displaySize.width)
        hasher.combine(displaySize.height)
        hasher.combine(representations.count)

        for representation in representations {
            // An unfamiliar or lazily drawn representation keeps using the
            // existing TIFF path, rather than assuming its image is static.
            guard let bitmap = representation as? NSBitmapImageRep,
                  !bitmap.isPlanar, bitmap.bytesPerPlane > 0,
                  let bytes = bitmap.bitmapData else { return nil }
            // Named device/calibrated spaces have fixed interpretation here.
            // Custom profiles keep the legacy path instead of serializing an
            // ICC profile (or accidentally ignoring a profile-only change).
            guard [.deviceRGB, .calibratedRGB, .deviceWhite, .calibratedWhite]
                .contains(bitmap.colorSpaceName) else { return nil }
            hasher.combine(bitmap.size.width)
            hasher.combine(bitmap.size.height)
            hasher.combine(bitmap.pixelsWide)
            hasher.combine(bitmap.pixelsHigh)
            hasher.combine(bitmap.bitsPerSample)
            hasher.combine(bitmap.samplesPerPixel)
            hasher.combine(bitmap.bitsPerPixel)
            hasher.combine(bitmap.bytesPerRow)
            hasher.combine(bitmap.hasAlpha)
            hasher.combine(bitmap.bitmapFormat.rawValue)
            hasher.combine(bitmap.colorSpaceName.rawValue)
            hasher.combine(bytes: UnsafeRawBufferPointer(start: bytes, count: bitmap.bytesPerPlane))
        }
        return hasher.finalize()
    }
}
