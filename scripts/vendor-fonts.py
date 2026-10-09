"""Vendor the existing Google Fonts assets for same-origin, offline-capable rendering.

Run explicitly when updating fonts; review assets, licenses and provenance changes.
Builds never contact a font service.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent / "public/fonts"
AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
SOURCES = {
    "inter": "https://fonts.googleapis.com/css2?family=Inter:wght@300..800&display=swap",
    "symbols": "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:FILL@0..1&display=block",
}
LICENSES = {
    "Inter-OFL.txt": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/OFL.txt",
    "Material-Symbols-LICENSE.txt": "https://raw.githubusercontent.com/google/material-design-icons/master/LICENSE",
}


def download(url):
    with urlopen(Request(url, headers={"User-Agent": AGENT}), timeout=45) as response:
        return response.read(12_000_000)


def family(item):
    name, source = item
    css = download(source).decode()
    faces = re.findall(r"(?:/\*[^*]*\*/\s*)?@font-face\s*\{[^}]+\}", css)
    if name == "inter":
        faces = [
            face for face in faces if "/* latin */" in face or "/* latin-ext */" in face
        ]
    if not faces:
        raise RuntimeError(f"No compatible font faces from {name}")
    metadata = []
    output = []
    for face in faces:
        url = re.search(r"url\((https://fonts.gstatic.com/[^)]+)\)", face).group(1)
        content = download(url)
        if not content.startswith(b"wOF2"):
            raise RuntimeError("Expected a WOFF2 font")
        digest = hashlib.sha256(content).hexdigest()
        filename = f"{name}-{digest[:12]}.woff2"
        (ROOT / filename).write_bytes(content)
        metadata.append(
            {"file": filename, "source": url, "sha256": digest, "bytes": len(content)}
        )
        output.append(face.replace(url, f"./{filename}"))
    return "\n".join(output), metadata


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(family, SOURCES.items()))
    for name, url in LICENSES.items():
        notice = download(url).decode("utf-8")
        (ROOT / name).write_text(
            "\n".join(line.rstrip() for line in notice.splitlines()) + "\n",
            encoding="utf-8",
        )
    (ROOT / "fonts.css").write_text(
        "\n".join(css for css, _ in results) + "\n", encoding="utf-8"
    )
    manifest = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "css_sources": SOURCES,
        "license_sources": LICENSES,
        "files": [item for _, values in results for item in values],
    }
    (ROOT / "provenance.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "font_files": len(manifest["files"]),
                "bytes": sum(x["bytes"] for x in manifest["files"]),
            }
        )
    )


if __name__ == "__main__":
    main()
