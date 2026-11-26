import Foundation

enum AssetLayer: String, CaseIterable {
    case mods = "Mods"
    case data = "Data"
    case bundle = "App Bundle"
}

struct LocalizedText {
    let value: String
    let layer: AssetLayer
}

struct AssetStore {
    let documentsURL: URL
    let bundledAssetsURL: URL

    func makeLocalDirectories() throws {
        for layer in [AssetLayer.data, .mods] {
            try FileManager.default.createDirectory(
                at: root(for: layer),
                withIntermediateDirectories: true
            )
        }
    }

    func firstAsset<Value>(
        at relativePath: String,
        decode: (Data) -> Value?
    ) -> (value: Value, layer: AssetLayer)? {
        for layer in AssetLayer.allCases {
            if let data = contents(at: relativePath, in: layer), let value = decode(data) {
                return (value, layer)
            }
        }
        return nil
    }

    func localizedStrings() -> [String: LocalizedText] {
        let decoder = JSONDecoder()
        var strings: [String: LocalizedText] = [:]

        for layer in AssetLayer.allCases.reversed() {
            guard let data = contents(at: "Localization/strings.json", in: layer),
                  let table = try? decoder.decode([String: String].self, from: data) else {
                continue
            }
            for (key, value) in table {
                strings[key] = LocalizedText(value: value, layer: layer)
            }
        }
        return strings
    }

    private func root(for layer: AssetLayer) -> URL {
        if layer == .bundle {
            return bundledAssetsURL
        }
        return documentsURL.appendingPathComponent(layer.rawValue, isDirectory: true)
    }

    private func contents(at relativePath: String, in layer: AssetLayer) -> Data? {
        let parts = relativePath.split(separator: "/", omittingEmptySubsequences: false)
        guard !relativePath.contains("\\"),
              parts.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }) else {
            return nil
        }

        let root = root(for: layer).standardizedFileURL.resolvingSymlinksInPath()
        let file = parts.reduce(root) { url, component in
            url.appendingPathComponent(String(component))
        }.standardizedFileURL.resolvingSymlinksInPath()

        guard file.path.hasPrefix(root.path + "/"),
              (try? file.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true else {
            return nil
        }
        return try? Data(contentsOf: file)
    }
}
