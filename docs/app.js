const fallback = {
  version: "v1.0.6",
  url: "https://github.com/gitlares/fs-pdf-compressor/releases/download/v1.0.6/FS-PDF-Compressor-1.0.6-arm64.dmg",
};

function applyRelease(release) {
  const asset = release.assets?.find(({ name }) => name.endsWith("-arm64.dmg"));
  if (!asset) return;

  for (const id of ["download-button", "download-button-bottom"]) {
    document.getElementById(id).href = asset.browser_download_url;
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
  document.getElementById(id).href = fallback.url;
}
document.getElementById("release-version").textContent = fallback.version;

fetch("https://api.github.com/repos/gitlares/fs-pdf-compressor/releases/latest")
  .then((response) => {
    if (!response.ok) throw new Error("Release lookup failed");
    return response.json();
  })
  .then(applyRelease)
  .catch(() => {});
