import Foundation
import Vision
import CoreGraphics

let input = FileHandle.standardInput
let output = FileHandle.standardOutput

func readLineData() -> Data? {
    var data = Data()
    while true {
        let next = input.readData(ofLength: 1)
        if next.isEmpty { return data.isEmpty ? nil : data }
        if next[0] == 10 { return data }
        data.append(next)
    }
}

func readExactly(_ count: Int) throws -> Data {
    var data = Data()
    while data.count < count {
        let chunk = input.readData(ofLength: count-data.count)
        if chunk.isEmpty { throw NSError(domain: "Truncated frame", code: 1) }
        data.append(chunk)
    }
    return data
}

func pixels(_ rect: CGRect, _ width: Int, _ height: Int) -> [Double] {
    return [rect.minX*Double(width), (1-rect.maxY)*Double(height),
            rect.width*Double(width), rect.height*Double(height)]
}

while let line = readLineData() {
    do {
        try autoreleasepool {
            let header = try JSONSerialization.jsonObject(with: line) as! [String: Any]
            let width = header["width"] as! Int
            let height = header["height"] as! Int
            guard width > 0 && height > 0 && width*height < 150_000_000 else {
                throw NSError(domain: "Invalid dimensions", code: 2)
            }
            let rgb = try readExactly(width*height*3)
            let provider = CGDataProvider(data: rgb as CFData)!
            let image = CGImage(width: width, height: height, bitsPerComponent: 8,
                bitsPerPixel: 24, bytesPerRow: width*3, space: CGColorSpaceCreateDeviceRGB(),
                bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.none.rawValue),
                provider: provider, decode: nil, shouldInterpolate: false, intent: .defaultIntent)!
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            request.recognitionLanguages = header["languages"] as? [String] ?? ["zh-Hans", "en-US"]
            request.usesLanguageCorrection = false
            request.minimumTextHeight = 0.002
            request.customWords = header["terms"] as? [String] ?? []
            try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
            var rows = [[String: Any]]()
            for observation in request.results ?? [] {
                guard let candidate = observation.topCandidates(1).first else { continue }
                var row: [String: Any] = ["text": candidate.string,
                    "confidence": candidate.confidence, "box": pixels(observation.boundingBox,width,height)]
                let normalized = candidate.string.precomposedStringWithCompatibilityMapping.lowercased().filter { !$0.isWhitespace }
                let terms = header["terms"] as? [String] ?? []
                let termHit = terms.contains { term in
                    normalized.contains(term.precomposedStringWithCompatibilityMapping.lowercased().filter { !$0.isWhitespace })
                }
                let regexHit = (header["regex"] as? [String] ?? []).contains { pattern in
                    guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else { return false }
                    return regex.firstMatch(in: candidate.string, range: NSRange(candidate.string.startIndex..., in: candidate.string)) != nil
                }
                if header["chars"] as? Bool == true && (termHit || regexHit || header["all_text"] as? Bool == true) {
                    var boxes: [Any] = []
                    // Unicode scalars keep indices aligned with Python code points.
                    let text = candidate.string
                    for idx in text.unicodeScalars.indices {
                        let next = text.unicodeScalars.index(after: idx)
                        if let box = try? candidate.boundingBox(for: idx..<next) {
                            boxes.append(pixels(box.boundingBox,width,height))
                        } else { boxes.append(NSNull()) }
                    }
                    row["chars"] = boxes
                }
                rows.append(row)
            }
            let result = try JSONSerialization.data(withJSONObject: ["rows": rows])
            output.write(result); output.write(Data([10]))
        }
    } catch {
        let result = try! JSONSerialization.data(withJSONObject: ["error": String(describing: error)])
        output.write(result); output.write(Data([10]))
    }
}
