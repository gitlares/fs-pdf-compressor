const fallback = {
  version: "v1.0.13",
  macosUrl: "https://github.com/gitlares/fs-pdf-compressor/releases/download/v1.0.13/FS-PDF-Compressor-1.0.13-arm64.dmg",
  windowsUrl: "https://github.com/gitlares/fs-pdf-compressor/releases/download/v1.0.13/FS-PDF-Compressor-1.0.13-windows-x86_64-setup.exe",
};

function applyRelease(release) {
  const macosAsset = release.assets?.find(({ name }) => name.endsWith("-arm64.dmg"));
  const windowsAsset = release.assets?.find(({ name }) => name.endsWith("-windows-x86_64-setup.exe"));

  if (macosAsset) {
    for (const id of ["download-button", "download-button-bottom"]) {
      document.getElementById(id).href = macosAsset.browser_download_url;
    }
  }
  if (windowsAsset) {
    for (const id of ["windows-download-button", "windows-download-button-bottom"]) {
      document.getElementById(id).href = windowsAsset.browser_download_url;
    }
  }
  document.getElementById("release-version").textContent = release.tag_name;

  const structuredData = document.getElementById("software-application-data");
  if (structuredData) {
    try {
      const graph = JSON.parse(structuredData.textContent);
      const application = graph["@graph"]?.find(
        (entity) => entity["@type"] === "SoftwareApplication",
      );
      if (application) {
        application.softwareVersion = release.tag_name.replace(/^v/, "");
        application.downloadUrl = release.html_url;
        application.releaseNotes = release.html_url;
        structuredData.textContent = JSON.stringify(graph);
      }
    } catch {
      // The static structured data remains valid if release enrichment fails.
    }
  }
}

for (const id of ["download-button", "download-button-bottom"]) {
  document.getElementById(id).href = fallback.macosUrl;
}
for (const id of ["windows-download-button", "windows-download-button-bottom"]) {
  document.getElementById(id).href = fallback.windowsUrl;
}
document.getElementById("release-version").textContent = fallback.version;

fetch("https://api.github.com/repos/gitlares/fs-pdf-compressor/releases/latest")
  .then((response) => {
    if (!response.ok) throw new Error("Release lookup failed");
    return response.json();
  })
  .then(applyRelease)
  .catch(() => {});
