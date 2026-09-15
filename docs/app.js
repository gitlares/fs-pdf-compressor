const fallback = {
  version: "v1.0.14",
  macosUrl: "https://github.com/gitlares/fs-pdf-compressor/releases/download/v1.0.14/FS-PDF-Compressor-1.0.14-arm64.dmg",
  windowsUrl: "https://github.com/gitlares/fs-pdf-compressor/releases/download/v1.0.14/FS-PDF-Compressor-1.0.14-windows-x86_64-setup.exe",
  linuxUrl: "https://github.com/gitlares/fs-pdf-compressor/releases/latest/download/FS-PDF-Compressor-x86_64.AppImage",
};

function detectedDesktopPlatform() {
  const userAgent = navigator.userAgent || "";
  const platform = navigator.userAgentData?.platform || navigator.platform || "";

  // Mobile devices and ChromeOS do not have a supported native download.
  if (/Android|iPhone|iPad|iPod|CrOS/i.test(`${userAgent} ${platform}`)) return null;
  if (/Mac/i.test(platform)) return "mac";
  if (/Win/i.test(platform)) return "windows";
  if (/Linux|X11/i.test(platform)) return "linux";
  return null;
}

function redirectFirstVisitToPlatform() {
  if (!document.documentElement.hasAttribute("data-platform-redirect")) return;

  const params = new URLSearchParams(window.location.search);
  if (params.get("platform") === "all") return;
  if (/bot|crawler|spider|slurp|preview|facebookexternalhit/i.test(navigator.userAgent)) return;

  try {
    const key = "fs-pdf-platform-redirected";
    if (sessionStorage.getItem(key)) return;
    const platform = detectedDesktopPlatform();
    if (!platform) return;
    sessionStorage.setItem(key, platform);
    window.location.replace(new URL(`${platform}/`, window.location.href));
  } catch {
    // If storage is unavailable, keep the complete platform chooser visible.
  }
}

redirectFirstVisitToPlatform();

function setHref(ids, url) {
  for (const id of ids) {
    const element = document.getElementById(id);
    if (element) element.href = url;
  }
}

function setVersion(version) {
  for (const element of document.querySelectorAll("[data-release-version]")) {
    element.textContent = version;
  }
}

function applyRelease(release) {
  const macosAsset = release.assets?.find(({ name }) => name.endsWith("-arm64.dmg"));
  const windowsAsset = release.assets?.find(({ name }) => name.endsWith("-windows-x86_64-setup.exe"));
  const linuxAsset = release.assets?.find(({ name }) => name.endsWith(".AppImage"));

  if (macosAsset) {
    setHref(["download-button", "download-button-bottom"], macosAsset.browser_download_url);
  }
  if (windowsAsset) {
    setHref(["windows-download-button", "windows-download-button-bottom"], windowsAsset.browser_download_url);
  }
  if (linuxAsset) {
    setHref(["linux-download-button", "linux-download-button-bottom"], linuxAsset.browser_download_url);
  }
  setVersion(release.tag_name);

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

setHref(["download-button", "download-button-bottom"], fallback.macosUrl);
setHref(["windows-download-button", "windows-download-button-bottom"], fallback.windowsUrl);
setHref(["linux-download-button", "linux-download-button-bottom"], fallback.linuxUrl);
setVersion(fallback.version);

fetch("https://api.github.com/repos/gitlares/fs-pdf-compressor/releases/latest")
  .then((response) => {
    if (!response.ok) throw new Error("Release lookup failed");
    return response.json();
  })
  .then(applyRelease)
  .catch(() => {});
