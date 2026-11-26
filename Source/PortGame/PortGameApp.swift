import CoreText
import Foundation
import SwiftUI

@main
struct PortGameApp: App {
    var body: some Scene {
        WindowGroup {
            PreviewScreen()
        }
    }
}

struct PreviewScreen: View {
    @Environment(\.scenePhase) private var scenePhase
    @ScaledMetric(relativeTo: .body) private var previewFontSize: CGFloat = 17
    @State private var strings: [String: LocalizedText] = [:]
    @State private var fontDescriptor: CTFontDescriptor?
    @State private var fontLayer: AssetLayer?
    @State private var folderError: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("ตัวอย่างข้อความ") {
                    if let title = strings["preview.title"] {
                        Text(verbatim: title.value)
                            .font(previewFont.bold())
                    }
                    if let body = strings["preview.body"] {
                        Text(verbatim: body.value)
                            .font(previewFont)
                    }
                }
                Section("แหล่งที่มาของไฟล์") {
                    LabeledContent("หัวข้อ", value: strings["preview.title"]?.layer.rawValue ?? "—")
                    LabeledContent("ข้อความ", value: strings["preview.body"]?.layer.rawValue ?? "—")
                    LabeledContent("ฟอนต์", value: fontLayer?.rawValue ?? "ระบบ iOS")
                }
                Section {
                    Button("โหลดไฟล์ใหม่", action: reload)
                    if let folderError {
                        Text(verbatim: folderError)
                            .foregroundStyle(.secondary)
                    }
                } footer: {
                    Text("วาง Data หรือ Mods ในแอปไฟล์ > บน iPhone/iPad ของฉัน > Port Game")
                }
            }
            .navigationTitle("Port Game")
        }
        .onChange(of: scenePhase, initial: true) { _, phase in
            if phase == .active {
                reload()
            }
        }
    }

    private var previewFont: Font {
        guard let fontDescriptor else { return .body }
        return Font(CTFontCreateWithFontDescriptor(fontDescriptor, previewFontSize, nil))
    }

    private func reload() {
        let bundledAssetsURL = Bundle.main.bundleURL.appendingPathComponent(
            "DefaultAssets",
            isDirectory: true
        )
        let store = AssetStore(
            documentsURL: URL.documentsDirectory,
            bundledAssetsURL: bundledAssetsURL
        )

        do {
            try store.makeLocalDirectories()
            folderError = nil
        } catch {
            folderError = "เปิดโฟลเดอร์ Data หรือ Mods ไม่สำเร็จ: \(error.localizedDescription)"
        }

        strings = store.localizedStrings()
        let font = store.firstAsset(at: "Fonts/Thai.ttf") { data in
            (CTFontManagerCreateFontDescriptorsFromData(data as CFData) as? [CTFontDescriptor])?.first
        }
        fontDescriptor = font?.value
        fontLayer = font?.layer
    }
}
