import AppKit
import Foundation
import Vision

struct OcrWord: Codable {
    let left: String
    let top: String
    let width: String
    let height: String
    let conf: String
    let text: String
}

struct OcrResponse: Codable {
    let text: String
    let text_json: [OcrWord]
    let confidence: Double
    let engine: String
}

func loadImage(at path: String) -> CGImage? {
    let url = URL(fileURLWithPath: path)
    guard let image = NSImage(contentsOf: url) else {
        return nil
    }

    var rect = NSRect(origin: .zero, size: image.size)
    return image.cgImage(forProposedRect: &rect, context: nil, hints: nil)
}

func buildRequest(languages: [String]) -> VNRecognizeTextRequest {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    if !languages.isEmpty {
        request.recognitionLanguages = languages
    }
    return request
}

func main() throws {
    guard CommandLine.arguments.count >= 2 else {
        throw NSError(domain: "apple_vision_ocr", code: 2, userInfo: [NSLocalizedDescriptionKey: "missing image path"])
    }

    let imagePath = CommandLine.arguments[1]
    let languageArg = CommandLine.arguments.count >= 3 ? CommandLine.arguments[2] : ""
    let languages = languageArg.split(separator: ",").map { String($0) }.filter { !$0.isEmpty }

    guard let cgImage = loadImage(at: imagePath) else {
        throw NSError(domain: "apple_vision_ocr", code: 3, userInfo: [NSLocalizedDescriptionKey: "failed to load image"])
    }

    let request = buildRequest(languages: languages)
    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try handler.perform([request])

    let observations = request.results ?? []
    var words: [OcrWord] = []
    var textParts: [String] = []
    var confidenceTotal = 0.0

    for observation in observations {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let text = candidate.string.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.isEmpty { continue }
        let box = observation.boundingBox
        let top = 1.0 - box.origin.y - box.size.height
        words.append(
            OcrWord(
                left: String(describing: box.origin.x),
                top: String(describing: top),
                width: String(describing: box.size.width),
                height: String(describing: box.size.height),
                conf: String(describing: candidate.confidence),
                text: text
            )
        )
        textParts.append(text)
        confidenceTotal += Double(candidate.confidence)
    }

    let payload = OcrResponse(
        text: textParts.joined(separator: " "),
        text_json: words,
        confidence: words.isEmpty ? 0.0 : confidenceTotal / Double(words.count),
        engine: "apple-vision"
    )
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.withoutEscapingSlashes]
    let data = try encoder.encode(payload)
    if let json = String(data: data, encoding: .utf8) {
        print(json)
    }
}

do {
    try main()
} catch {
    fputs("\(error.localizedDescription)\n", stderr)
    exit(1)
}
