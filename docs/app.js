const fallback = {
  version: "v1.0.4",
  url: "https://github.com/gitlares/fs-pdf-compressor/releases/download/v1.0.4/FS-PDF-Compressor-1.0.4-arm64.dmg",
};

function applyRelease(release) {
  const asset = release.assets?.find(({ name }) => name.endsWith("-arm64.dmg"));
  if (!asset) return;

  for (const id of ["download-button", "download-button-bottom"]) {
    document.getElementById(id).href = asset.browser_download_url;
  }
  document.getElementById("release-version").textContent = release.tag_name;
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
