"""Copy bundled runtime dependency license texts into a release package."""

from __future__ import annotations

import argparse
import importlib.metadata
import re
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    requirements = []
    for line in (args.project_root / "requirements.lock").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==", line)
        if match:
            requirements.append(match.group(1))
    requirements.append("PyInstaller")  # Its bootloader is part of the executable.

    args.output.mkdir(parents=True, exist_ok=True)
    rows = ["# Third-party license inventory", "", "Copied from the pinned Windows build environment.", ""]
    for name in requirements:
        distribution = importlib.metadata.distribution(name)
        label = _license_label(distribution)
        package_directory = args.output / f"{distribution.metadata['Name']}-{distribution.version}"
        files = [
            file
            for file in distribution.files or ()
            if "/licenses/" in f"/{file.as_posix()}".lower()
            or Path(file.name).name.lower() in {"license", "license.txt", "copying"}
        ]
        copied = 0
        license_source: Path | None = None
        for file in files:
            source = Path(distribution.locate_file(file))
            if source.is_file():
                license_source = source
                relative = Path(file.name) if "licenses" not in file.as_posix().lower() else Path(*file.parts[-2:])
                destination = package_directory / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                copied += 1
        if copied == 0:
            fallback = args.project_root / "packaging" / "licenses" / f"{name}-0.1.0.LICENSE.txt"
            if fallback.is_file():
                package_directory.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fallback, package_directory / "LICENSE.txt")
                license_source = fallback
                copied = 1
        if copied == 0:
            raise RuntimeError(f"No license text found for {distribution.metadata['Name']}")
        if not label:
            label = _license_from_text(license_source) if license_source else None
        if not label:
            label = "License metadata unavailable; review bundled LICENSE text"
        if name == "proxy_tools":
            label = "BSD (upstream license; PyPI metadata declares MIT)"
        rows.append(f"- **{distribution.metadata['Name']} {distribution.version}:** {label} — `{package_directory.name}`")

    (args.output / "INVENTORY.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _license_classifier(distribution: importlib.metadata.Distribution) -> str | None:
    classifiers = distribution.metadata.get_all("Classifier") or []
    for classifier in classifiers:
        if classifier.startswith("License :: OSI Approved ::"):
            return classifier.rsplit("::", 1)[-1].strip()
    return None


def _license_label(distribution: importlib.metadata.Distribution) -> str | None:
    expression = distribution.metadata.get("License-Expression")
    if expression:
        return expression
    license_field = (distribution.metadata.get("License") or "").strip()
    if license_field and "\n" not in license_field and len(license_field) <= 180:
        return license_field
    classifier = _license_classifier(distribution)
    if classifier == "Apache Software License":
        return "Apache-2.0"
    return classifier


def _license_from_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    first_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[:6]
    heading = " ".join(line.strip() for line in first_lines if line.strip()).casefold()
    if "mit license" in heading:
        return "MIT"
    if "apache license" in heading:
        return "Apache-2.0"
    if "gnu general public license" in heading:
        return "GNU GPL; see included license text"
    if "bsd" in heading:
        return "BSD; see included license text"
    return None


if __name__ == "__main__":
    main()
