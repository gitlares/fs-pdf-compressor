cask "fs-pdf-compressor" do
  version "1.0.7"
  sha256 "d6194776183f06ad3c4cf8c702992306ed79e51867cef7f5fee8db2475932067"

  url "https://github.com/gitlares/fs-pdf-compressor/releases/download/v#{version}/FS-PDF-Compressor-#{version}-arm64.dmg",
      verified: "github.com/gitlares/fs-pdf-compressor/"
  name "FS PDF Compressor"
  desc "Compress PDF files locally"
  homepage "https://gitlares.github.io/fs-pdf-compressor/"

  depends_on macos: ">= :sonoma"
  depends_on arch: :arm64

  livecheck do
    url "https://github.com/gitlares/fs-pdf-compressor/releases"
    strategy :github_latest
  end

  app "FS PDF Compressor.app"
end
