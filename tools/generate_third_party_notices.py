# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

import argparse
import email
import hashlib
import json
import os
import re
import zipfile
import xml.etree.ElementTree as element_tree
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import quote

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement


ROOT = Path(__file__).resolve().parents[1]
LICENSE_FILE_PATTERN = re.compile(r"^(licen[cs]e|copying|notice|copyright)([._-].*)?$", re.IGNORECASE)
ANDROID_LOCK_FILE = "third_party_dependencies.json"
ANDROID_INPUTS = (
    "settings.gradle.kts",
    "build.gradle.kts",
    "gradle/libs.versions.toml",
    "app/build.gradle.kts",
)
GENERATION_NOTE = (
    "Generation note: This notice is produced from committed dependency locks and package metadata. "
    "Regenerate and review it whenever dependencies change; authoritative upstream terms continue to control.",
    "生成说明：本声明依据已提交的依赖锁文件和软件包元数据生成。依赖发生变化时必须重新生成并复核；"
    "各上游发布的正式条款仍具有最终效力。",
)
NETEASE_SERVICE_DISCLOSURE = (
    "NetEase service and content boundary: The original code in Love Journal's netease-api helper is licensed "
    "under AGPL-3.0-only. That license covers only the project code and grants no rights to NetEase Cloud Music "
    "APIs or services, accounts, music or other content, data, or trademarks. The helper uses unofficial "
    "interfaces; access and use may be limited by current service terms, account rules, content licenses, "
    "applicable law, and region. Operators must independently confirm authorization and compliance. This "
    "disclosure describes external legal and service risk and does not add a field-of-use restriction to the "
    "AGPL license for Love Journal code.",
    "网易云音乐服务与内容边界：Love Journal 的 netease-api 辅助模块原创代码按 AGPL-3.0-only 授权。"
    "该授权仅覆盖项目代码，不授予对网易云音乐 API 或服务、账号、音乐及其他内容、数据或商标的任何权利。"
    "本模块使用非官方接口，其访问和使用可能受到届时有效的服务条款、账号规则、内容许可、适用法律及地区限制。"
    "运营者须自行确认是否获得授权并满足合规要求。本说明披露的是外部法律与服务风险，不对 Love Journal 代码的 "
    "AGPL 授权增加用途限制。",
)

Disclosure = tuple[str, str]


@dataclass
class PackageRecord:
    name: str
    version: str
    license_name: str
    source: str
    license_url: str = ""
    license_files: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class DistributionMetadata:
    name: str
    version: str
    message: email.message.Message
    license_files: list[tuple[str, str]]


@dataclass
class MavenMetadata:
    license_names: list[str]
    license_urls: list[str]
    source: str


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = "\n".join(line.rstrip() for line in content.splitlines()).strip()
    path.write_text(normalized + "\n", encoding="utf-8", newline="\n")


def deduplicate_license_files(files: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    result = []
    seen = set()
    for filename, content in files:
        content = content.strip()
        if not content:
            continue
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if digest not in seen:
            seen.add(digest)
            result.append((filename, content))
    return result


def is_license_filename(name: str) -> bool:
    basename = PurePosixPath(name.replace("\\", "/")).name
    if LICENSE_FILE_PATTERN.match(basename):
        return True
    return basename.lower() == "third_party_licenses.txt"


def find_license_files(directory: Path, *, recursive: bool = False) -> list[tuple[str, str]]:
    if not directory.is_dir():
        return []
    candidates: list[Path] = []
    if recursive:
        candidates.extend(path for path in directory.rglob("*") if path.is_file() and is_license_filename(path.name))
    else:
        candidates.extend(path for path in directory.iterdir() if path.is_file() and is_license_filename(path.name))
        licenses_directory = directory / "licenses"
        if licenses_directory.is_dir():
            candidates.extend(path for path in licenses_directory.rglob("*") if path.is_file())
    return deduplicate_license_files((path.name, read_text(path)) for path in sorted(candidates, key=lambda item: str(item).lower()))


def archive_license_files(archive_path: Path) -> list[tuple[str, str]]:
    if not archive_path.is_file():
        return []
    try:
        with zipfile.ZipFile(archive_path) as archive:
            files = []
            for name in archive.namelist():
                if archive.getinfo(name).is_dir() or not is_license_filename(name):
                    continue
                data = archive.read(name)
                if len(data) > 4 * 1024 * 1024:
                    continue
                files.append((PurePosixPath(name).name, data.decode("utf-8", errors="replace")))
    except (OSError, zipfile.BadZipFile):
        return []
    return deduplicate_license_files(files)


def package_name_from_lock_path(lock_path: str) -> str:
    tail = lock_path.replace("\\", "/").rsplit("node_modules/", 1)[-1]
    parts = tail.split("/")
    return "/".join(parts[:2]) if parts[0].startswith("@") else parts[0]


def repository_url(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("url", "")
    if not isinstance(value, str):
        return ""
    url = value.removeprefix("scm:git:").removeprefix("git+")
    if url.startswith("git://github.com/"):
        url = "https://github.com/" + url[len("git://github.com/") :]
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:") :]
    return url.removesuffix(".git")


def npm_license(locked: dict, installed: dict) -> tuple[str, str]:
    value = locked.get("license") or installed.get("license")
    if value:
        return str(value), ""
    legacy = installed.get("licenses")
    if isinstance(legacy, list):
        identifiers = [item.get("type") for item in legacy if isinstance(item, dict) and item.get("type")]
        urls = [item.get("url") for item in legacy if isinstance(item, dict) and item.get("url")]
        if identifiers:
            return " OR ".join(str(item) for item in identifiers), " | ".join(str(item) for item in urls)
    return "NOASSERTION", ""


def npm_records(project: Path) -> list[PackageRecord]:
    lock_path = project / "package-lock.json"
    modules_path = project / "node_modules"
    if not lock_path.is_file() or not modules_path.is_dir():
        raise RuntimeError(f"Install npm dependencies before generating notices: {project}")
    lock = json.loads(read_text(lock_path))
    records = []
    for relative_path, locked in lock.get("packages", {}).items():
        if not relative_path or locked.get("link") or not locked.get("version"):
            continue
        package_directory = project / Path(relative_path)
        package_json_path = package_directory / "package.json"
        installed = json.loads(read_text(package_json_path)) if package_json_path.is_file() else {}
        name = installed.get("name") or locked.get("name") or package_name_from_lock_path(relative_path)
        license_name, license_url = npm_license(locked, installed)
        source = (
            repository_url(installed.get("repository"))
            or repository_url(locked.get("repository"))
            or installed.get("homepage", "")
            or locked.get("resolved", "")
        )
        records.append(
            PackageRecord(
                name=name,
                version=str(locked["version"]),
                license_name=str(license_name),
                source=str(source),
                license_url=str(license_url),
                license_files=find_license_files(package_directory),
            )
        )
    return sorted(records, key=lambda item: (item.name.lower(), item.version))


def metadata_license(message: email.message.Message) -> str:
    expression = message.get("License-Expression")
    if expression and expression.strip().upper() not in {"UNKNOWN", "N/A"}:
        return " ".join(expression.split())
    value = message.get("License")
    if value and value.strip().upper() not in {"UNKNOWN", "N/A"}:
        normalized = " ".join(value.split())
        detected = license_from_files([("License metadata", normalized)])
        return detected if detected != "NOASSERTION" else normalized
    classifier_map = {
        "Apache Software License": "Apache-2.0",
        "BSD License": "BSD",
        "GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0-only",
        "ISC License (ISCL)": "ISC",
        "MIT License": "MIT",
        "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
        "Python Software Foundation License": "PSF-2.0",
    }
    for classifier in message.get_all("Classifier", []):
        for label, identifier in classifier_map.items():
            if label in classifier:
                return identifier
    return "NOASSERTION"


def license_from_files(files: list[tuple[str, str]]) -> str:
    for _, content in files:
        normalized = content.lower()
        if "apache license" in normalized and "version 2.0, january 2004" in normalized:
            return "Apache-2.0"
        if "mozilla public license version 2.0" in normalized:
            return "MPL-2.0"
        if "the mit license (mit)" in normalized or normalized.startswith("mit license"):
            return "MIT"
        if "isc license" in normalized:
            return "ISC"
    return "NOASSERTION"


def metadata_source(message: email.message.Message) -> str:
    project_urls = []
    for value in message.get_all("Project-URL", []):
        label, separator, url = value.partition(",")
        if separator:
            project_urls.append((label.strip().lower(), url.strip()))
    for wanted in ("source", "repository", "code", "homepage"):
        for label, url in project_urls:
            if wanted in label:
                return repository_url(url)
    return repository_url(message.get("Home-page", ""))


def metadata_license_url(message: email.message.Message) -> str:
    for value in message.get_all("Project-URL", []):
        label, separator, url = value.partition(",")
        if separator and "license" in label.lower():
            return url.strip()
    return ""


def find_site_packages(project: Path, override: Path | None) -> Path:
    if override is not None:
        if not override.is_dir():
            raise RuntimeError(f"Python site-packages directory does not exist: {override}")
        return override
    venv = project / ".venv"
    candidates = [venv / "Lib" / "site-packages"]
    candidates.extend((venv / "lib").glob("python*/site-packages"))
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise RuntimeError(
        f"Install the locked Python dependencies before generating notices: {project}. "
        "Use --python-wheel-directory when generating from downloaded wheels."
    )


def site_distributions(site_packages: Path) -> dict[str, DistributionMetadata]:
    distributions: dict[str, DistributionMetadata] = {}
    for metadata_path in site_packages.glob("*.dist-info/METADATA"):
        message = email.message_from_string(read_text(metadata_path))
        name = message.get("Name")
        version = message.get("Version")
        if not name or not version:
            continue
        key = normalize_name(name)
        if key in distributions:
            raise RuntimeError(f"Duplicate Python distribution metadata for {name}: {site_packages}")
        distributions[key] = DistributionMetadata(
            name=name,
            version=version,
            message=message,
            license_files=find_license_files(metadata_path.parent, recursive=True),
        )
    return distributions


def wheel_distributions(wheel_directory: Path) -> dict[str, DistributionMetadata]:
    if not wheel_directory.is_dir():
        raise RuntimeError(f"Python wheel directory does not exist: {wheel_directory}")
    distributions: dict[str, DistributionMetadata] = {}
    for wheel_path in sorted(wheel_directory.glob("*.whl"), key=lambda item: item.name.lower()):
        with zipfile.ZipFile(wheel_path) as wheel:
            metadata_names = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
            if len(metadata_names) != 1:
                raise RuntimeError(f"Wheel has no unique METADATA file: {wheel_path}")
            message = email.message_from_string(wheel.read(metadata_names[0]).decode("utf-8", errors="replace"))
            name = message.get("Name")
            version = message.get("Version")
            if not name or not version:
                raise RuntimeError(f"Wheel metadata lacks name or version: {wheel_path}")
            files = []
            for member in wheel.namelist():
                if not is_license_filename(member):
                    continue
                data = wheel.read(member)
                if len(data) <= 4 * 1024 * 1024:
                    files.append((PurePosixPath(member).name, data.decode("utf-8", errors="replace")))
        key = normalize_name(name)
        existing = distributions.get(key)
        if existing and existing.version != version:
            raise RuntimeError(f"Wheel directory contains multiple versions of {name}")
        distributions[key] = DistributionMetadata(
            name=name,
            version=version,
            message=message,
            license_files=deduplicate_license_files(files),
        )
    return distributions


def linux_python312_environment() -> dict[str, str]:
    environment = default_environment()
    environment.update(
        {
            "implementation_name": "cpython",
            "implementation_version": "3.12.0",
            "os_name": "posix",
            "platform_machine": "x86_64",
            "platform_python_implementation": "CPython",
            "platform_release": "",
            "platform_system": "Linux",
            "platform_version": "",
            "python_full_version": "3.12.0",
            "python_version": "3.12",
            "sys_platform": "linux",
        }
    )
    return environment


def parse_requirements(path: Path) -> list[Requirement]:
    requirements = []
    for line_number, raw_line in enumerate(read_text(path).splitlines(), start=1):
        clean = raw_line.split("#", 1)[0].strip()
        if not clean:
            continue
        if clean.startswith(("-r", "--requirement", "-c", "--constraint")):
            raise RuntimeError(f"Nested requirement files are not supported in {path}:{line_number}")
        try:
            requirements.append(Requirement(clean))
        except InvalidRequirement as error:
            raise RuntimeError(f"Invalid requirement in {path}:{line_number}: {clean}") from error
    return requirements


def requirement_applies(requirement: Requirement, environment: dict[str, str]) -> bool:
    if requirement.marker is None:
        return True
    return requirement.marker.evaluate({**environment, "extra": ""})


def source_requirements_hash(project: Path) -> str:
    return hashlib.sha256((project / "requirements.txt").read_bytes()).hexdigest()


def locked_requirement_entries(lock_path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(read_text(lock_path).splitlines(), start=1):
        clean = raw_line.split("#", 1)[0].strip()
        if not clean:
            continue
        try:
            requirement = Requirement(clean)
        except InvalidRequirement as error:
            raise RuntimeError(f"Invalid requirement lock entry in {lock_path}:{line_number}: {clean}") from error
        versions = list(requirement.specifier)
        if requirement.url or len(versions) != 1 or versions[0].operator != "==":
            raise RuntimeError(f"Lock entries must use one exact == version: {lock_path}:{line_number}")
        key = normalize_name(requirement.name)
        version = versions[0].version
        if key in entries and entries[key] != version:
            raise RuntimeError(f"Lock contains multiple versions of {requirement.name}")
        entries[key] = version
    if not entries:
        raise RuntimeError(f"Python lock file has no package entries: {lock_path}")
    return entries


def lock_source_hash(lock_path: Path) -> str:
    prefix = "# Source requirements SHA256: "
    for line in read_text(lock_path).splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def validate_lock_against_source(project: Path, locked: dict[str, str]) -> None:
    lock_path = project / "requirements.lock"
    expected_hash = source_requirements_hash(project)
    actual_hash = lock_source_hash(lock_path)
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"{lock_path} does not match requirements.txt. Refresh the Python lock and notices before publishing."
        )
    environment = linux_python312_environment()
    errors = []
    for requirement in parse_requirements(project / "requirements.txt"):
        if not requirement_applies(requirement, environment):
            continue
        version = locked.get(normalize_name(requirement.name))
        if version is None:
            errors.append(f"{requirement.name} is missing")
        elif requirement.specifier and not requirement.specifier.contains(version, prereleases=True):
            errors.append(f"{requirement.name}=={version} does not satisfy {requirement.specifier}")
    if errors:
        raise RuntimeError("Python lock does not satisfy requirements.txt: " + "; ".join(errors))


def write_python_lock(project: Path, distributions: dict[str, DistributionMetadata]) -> None:
    environment = linux_python312_environment()
    direct_errors = []
    for requirement in parse_requirements(project / "requirements.txt"):
        if not requirement_applies(requirement, environment):
            continue
        distribution = distributions.get(normalize_name(requirement.name))
        if distribution is None:
            direct_errors.append(f"{requirement.name} is absent from the downloaded wheel set")
        elif requirement.specifier and not requirement.specifier.contains(distribution.version, prereleases=True):
            direct_errors.append(f"{requirement.name}=={distribution.version} does not satisfy {requirement.specifier}")
    if direct_errors:
        raise RuntimeError("Cannot create Python lock: " + "; ".join(direct_errors))
    lines = [
        "# Generated by tools/generate_third_party_notices.py from a resolved Linux CPython 3.12 wheel set.",
        f"# Source requirements SHA256: {source_requirements_hash(project)}",
        "# Do not edit by hand. Refresh the wheel set, lock, and notices together when dependencies change.",
        "",
    ]
    lines.extend(
        f"{distribution.name}=={distribution.version}"
        for distribution in sorted(distributions.values(), key=lambda item: (normalize_name(item.name), item.version))
    )
    write_text(project / "requirements.lock", "\n".join(lines))


def python_records(
    project: Path,
    *,
    site_packages: Path | None = None,
    wheel_directory: Path | None = None,
) -> list[PackageRecord]:
    lock_path = project / "requirements.lock"
    if not lock_path.is_file():
        raise RuntimeError(f"Python lock file is required before generating notices: {lock_path}")
    if wheel_directory is not None and site_packages is not None:
        raise RuntimeError("Use either a Python wheel directory or site-packages, not both")
    distributions = wheel_distributions(wheel_directory) if wheel_directory else site_distributions(find_site_packages(project, site_packages))
    locked = locked_requirement_entries(lock_path)
    validate_lock_against_source(project, locked)
    missing = []
    mismatched = []
    records = []
    for normalized, expected_version in sorted(locked.items()):
        distribution = distributions.get(normalized)
        if distribution is None:
            missing.append(normalized)
            continue
        if distribution.version != expected_version:
            mismatched.append(f"{distribution.name}: expected {expected_version}, found {distribution.version}")
            continue
        license_name = metadata_license(distribution.message)
        if license_name == "NOASSERTION":
            license_name = license_from_files(distribution.license_files)
        records.append(
            PackageRecord(
                name=distribution.name,
                version=distribution.version,
                license_name=license_name,
                source=metadata_source(distribution.message),
                license_url=metadata_license_url(distribution.message),
                license_files=distribution.license_files,
            )
        )
    if missing or mismatched:
        details = []
        if missing:
            details.append("missing metadata for " + ", ".join(missing))
        if mismatched:
            details.append("version mismatches: " + "; ".join(mismatched))
        raise RuntimeError("Python notice generation stopped: " + " | ".join(details))
    return sorted(records, key=lambda item: (item.name.lower(), item.version))


def android_input_hash(project: Path) -> str:
    digest = hashlib.sha256()
    for relative_path in ANDROID_INPUTS:
        path = project / relative_path
        if not path.is_file():
            raise RuntimeError(f"Android input required for license inventory is missing: {path}")
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(element: element_tree.Element, name: str) -> str:
    for child in list(element):
        if local_name(child.tag) == name and child.text:
            return child.text.strip()
    return ""


def child_element(element: element_tree.Element, name: str) -> element_tree.Element | None:
    for child in list(element):
        if local_name(child.tag) == name:
            return child
    return None


def normalize_maven_license(value: str) -> str:
    normalized = " ".join(value.split())
    key = normalized.lower()
    if "apache" in key and "2.0" in key:
        return "Apache-2.0"
    if key in {"bsd-3-clause", "bsd 3-clause license", "bsd 3 clause license"}:
        return "BSD-3-Clause"
    if key in {"mit", "mit license"}:
        return "MIT"
    if key in {"isc", "isc license"}:
        return "ISC"
    if "android software development kit license" in key:
        return "Android Software Development Kit License"
    return normalized


def gradle_user_home() -> Path:
    return Path(os.environ.get("GRADLE_USER_HOME", Path.home() / ".gradle"))


def find_maven_pom(cache_root: Path, group: str, module: str, version: str) -> Path | None:
    directory = cache_root / "caches" / "modules-2" / "files-2.1" / group / module / version
    if not directory.is_dir():
        return None
    return next(iter(sorted(directory.rglob("*.pom"), key=lambda item: str(item).lower())), None)


def maven_metadata(
    cache_root: Path,
    group: str,
    module: str,
    version: str,
    *,
    cache: dict[tuple[str, str, str], MavenMetadata],
    visiting: set[tuple[str, str, str]],
) -> MavenMetadata:
    coordinate = (group, module, version)
    if coordinate in cache:
        return cache[coordinate]
    if coordinate in visiting:
        raise RuntimeError(f"Cyclic Maven parent POM while reading {group}:{module}:{version}")
    pom_path = find_maven_pom(cache_root, group, module, version)
    if pom_path is None:
        raise RuntimeError(f"Maven POM is missing from the Gradle cache: {group}:{module}:{version}")
    visiting.add(coordinate)
    root = element_tree.fromstring(read_text(pom_path))
    licenses_node = child_element(root, "licenses")
    license_names = []
    license_urls = []
    if licenses_node is not None:
        for license_node in list(licenses_node):
            if local_name(license_node.tag) != "license":
                continue
            name = child_text(license_node, "name")
            url = child_text(license_node, "url")
            if name:
                license_names.append(normalize_maven_license(name))
            if url:
                license_urls.append(url)
    scm = child_element(root, "scm")
    source = repository_url(child_text(scm, "url")) if scm is not None else ""
    if not source:
        source = repository_url(child_text(root, "url"))
    parent = child_element(root, "parent")
    parent_metadata = None
    if parent is not None:
        parent_group = child_text(parent, "groupId")
        parent_module = child_text(parent, "artifactId")
        parent_version = child_text(parent, "version")
        if parent_group and parent_module and parent_version and "${" not in parent_version:
            parent_metadata = maven_metadata(
                cache_root,
                parent_group,
                parent_module,
                parent_version,
                cache=cache,
                visiting=visiting,
            )
    if not license_names and parent_metadata is not None:
        license_names = parent_metadata.license_names
        license_urls = parent_metadata.license_urls
    if not source and parent_metadata is not None:
        source = parent_metadata.source
    visiting.remove(coordinate)
    metadata = MavenMetadata(
        license_names=list(dict.fromkeys(license_names)),
        license_urls=list(dict.fromkeys(license_urls)),
        source=source,
    )
    cache[coordinate] = metadata
    return metadata


def load_release_artifact_inventory(project: Path) -> list[dict[str, str]]:
    inventory_path = project / "app" / "build" / "reports" / "license-inventory" / "release-runtime-artifacts.json"
    if not inventory_path.is_file():
        raise RuntimeError(
            "Android release inventory is missing. Run `cd Android && ./gradlew :app:exportReleaseLicenseInventory` first."
        )
    data = json.loads(read_text(inventory_path))
    if data.get("schema_version") != 1 or data.get("configuration") != "releaseRuntimeClasspath":
        raise RuntimeError(f"Unexpected Android release inventory format: {inventory_path}")
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError(f"Android release inventory has no artifacts: {inventory_path}")
    result = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise RuntimeError(f"Invalid Android artifact entry: {inventory_path}")
        required = ("group", "module", "version", "file")
        if any(not isinstance(artifact.get(key), str) or not artifact[key] for key in required):
            raise RuntimeError(f"Incomplete Android artifact entry: {artifact}")
        result.append({key: artifact[key] for key in required})
    return result


def refresh_android_lock(project: Path) -> list[PackageRecord]:
    artifacts = load_release_artifact_inventory(project)
    cache_root = gradle_user_home()
    metadata_cache: dict[tuple[str, str, str], MavenMetadata] = {}
    records = []
    for artifact in artifacts:
        metadata = maven_metadata(
            cache_root,
            artifact["group"],
            artifact["module"],
            artifact["version"],
            cache=metadata_cache,
            visiting=set(),
        )
        if not metadata.license_names:
            raise RuntimeError(
                "Maven metadata does not declare an inheritable license for Android runtime artifact: "
                f"{artifact['group']}:{artifact['module']}:{artifact['version']}"
            )
        records.append(
            PackageRecord(
                name=f"{artifact['group']}:{artifact['module']}",
                version=artifact["version"],
                license_name="; ".join(metadata.license_names),
                source=metadata.source,
                license_url=" | ".join(metadata.license_urls),
                license_files=archive_license_files(Path(artifact["file"])),
            )
        )
    records = sorted(records, key=lambda item: (item.name.lower(), item.version))
    serialized = {
        "schema_version": 1,
        "variant": "release",
        "configuration": "releaseRuntimeClasspath",
        "inputs_sha256": android_input_hash(project),
        "artifacts": [
            {
                "name": record.name,
                "version": record.version,
                "license": record.license_name,
                "license_url": record.license_url,
                "source": record.source,
                "license_files": [{"name": name, "text": text} for name, text in record.license_files],
            }
            for record in records
        ],
    }
    write_text(project / ANDROID_LOCK_FILE, json.dumps(serialized, ensure_ascii=False, indent=2))
    return records


def android_records(project: Path) -> list[PackageRecord]:
    lock_path = project / ANDROID_LOCK_FILE
    if not lock_path.is_file():
        raise RuntimeError(f"Android resolved dependency lock is required: {lock_path}")
    data = json.loads(read_text(lock_path))
    if data.get("schema_version") != 1 or data.get("configuration") != "releaseRuntimeClasspath":
        raise RuntimeError(f"Unexpected Android dependency lock format: {lock_path}")
    if data.get("inputs_sha256") != android_input_hash(project):
        raise RuntimeError(
            f"{lock_path} is stale for the current Android build inputs. "
            "Refresh the release inventory and notices before publishing."
        )
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError(f"Android dependency lock has no artifacts: {lock_path}")
    records = []
    for artifact in artifacts:
        files = artifact.get("license_files", [])
        if not isinstance(files, list):
            raise RuntimeError(f"Invalid Android license files in {lock_path}")
        records.append(
            PackageRecord(
                name=str(artifact["name"]),
                version=str(artifact["version"]),
                license_name=str(artifact["license"]),
                source=str(artifact.get("source", "")),
                license_url=str(artifact.get("license_url", "")),
                license_files=deduplicate_license_files(
                    (str(item["name"]), str(item["text"]))
                    for item in files
                    if (
                        isinstance(item, dict)
                        and "name" in item
                        and "text" in item
                        and is_license_filename(str(item["name"]))
                    )
                ),
            )
        )
    return sorted(records, key=lambda item: (item.name.lower(), item.version))


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def source_cell(source: str) -> str:
    if not source:
        return "Not declared"
    if source.startswith(("https://", "http://")):
        safe = source.replace(" ", "%20")
        return f"<{safe}>"
    return escape_cell(source)


def inventory_section(title: str, records: list[PackageRecord]) -> str:
    lines = [
        f"## {title}",
        "",
        "| Package | Version | Declared license(s) | License source | Project source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in records:
        lines.append(
            f"| {escape_cell(record.name)} | {escape_cell(record.version)} | "
            f"{escape_cell(record.license_name)} | {source_cell(record.license_url)} | {source_cell(record.source)} |"
        )
    return "\n".join(lines)


def collect_license_texts(records: list[PackageRecord]) -> dict[str, tuple[str, list[str]]]:
    collected: dict[str, tuple[str, list[str]]] = {}
    for record in records:
        for filename, content in record.license_files:
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            label = f"{record.name} {record.version} ({filename})"
            if digest in collected:
                collected[digest][1].append(label)
            else:
                collected[digest] = (content, [label])
    return collected


def find_apache_license(records: list[PackageRecord]) -> str:
    for record in records:
        for _, content in record.license_files:
            if "Apache License" in content and "Version 2.0, January 2004" in content:
                return content
    raise RuntimeError("Could not locate a local copy of the Apache License 2.0 text")


def license_text_section(records: list[PackageRecord], extra_texts: list[tuple[str, str]] | None = None) -> str:
    collected = collect_license_texts(records)
    for label, content in extra_texts or []:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if digest in collected:
            collected[digest][1].append(label)
        else:
            collected[digest] = (content, [label])
    lines = ["## Available license and notice texts", ""]
    ordered = sorted(collected.values(), key=lambda item: item[1][0].lower())
    if not ordered:
        lines.append("No license or notice text files were available from the resolved artifacts.")
        return "\n".join(lines)
    for index, (content, labels) in enumerate(ordered, start=1):
        lines.extend(
            [
                f"### Text {index}",
                "",
                "Applies to: " + "; ".join(sorted(labels, key=str.lower)),
                "",
                "```text",
                content,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def android_sdk_disclosure(records: list[PackageRecord]) -> Disclosure | None:
    external = [
        record for record in records if "Android Software Development Kit License" in record.license_name
    ]
    if not external:
        return None
    terms_url = next((record.license_url for record in external if record.license_url), "https://developer.android.com/studio/terms")
    return (
        f"Android external SDK boundary: The resolved Android binary includes {len(external)} Google Play "
        "services/Firebase artifacts whose Maven metadata declares the Android Software Development Kit License. "
        f"Those external components are not covered by Love Journal's AGPL license and remain subject to the "
        f"current Android SDK terms at {terms_url}. Consequently, the distributed Android binary is not composed "
        "exclusively of open-source software, although Love Journal's original source code remains AGPL-licensed.",
        f"Android 外部 SDK 边界：当前解析的 Android 二进制包含 {len(external)} 个 Maven 元数据声明适用 "
        f"Android Software Development Kit License 的 Google Play 服务/Firebase 构件。这些外部组件不属于 "
        f"Love Journal 的 AGPL 授权范围，仍受 {terms_url} 所列届时有效的 Android SDK 条款约束。"
        "因此，发行的 Android 二进制并非完全由开源软件组成，但 Love Journal 的原创源代码仍按 AGPL 授权。",
    )


COPYLEFT_LICENSE_PATTERN = re.compile(r"(?<![A-Za-z])(?:A?GPL|LGPL|MPL|EPL|CDDL)(?![A-Za-z])", re.IGNORECASE)
UNKNOWN_LICENSES = {"", "N/A", "NOASSERTION", "UNKNOWN", "UNLICENSED"}


def validate_license_inventory(sections: list[tuple[str, list[PackageRecord]]]) -> None:
    unknown = []
    missing_copyleft_source = []
    missing_external_terms = []
    for component, records in sections:
        for record in records:
            license_name = record.license_name.strip()
            label = f"{component}: {record.name}@{record.version}"
            if license_name.upper() in UNKNOWN_LICENSES:
                unknown.append(label)
            if COPYLEFT_LICENSE_PATTERN.search(license_name) and not record.source.strip():
                missing_copyleft_source.append(label)
            if "Android Software Development Kit License" in license_name and not record.license_url.strip():
                missing_external_terms.append(label)

    problems = []
    if unknown:
        problems.append("unknown license declarations: " + ", ".join(unknown))
    if missing_copyleft_source:
        problems.append("copyleft dependencies without a source link: " + ", ".join(missing_copyleft_source))
    if missing_external_terms:
        problems.append("external Android SDK dependencies without a terms link: " + ", ".join(missing_external_terms))
    if problems:
        raise RuntimeError("License inventory validation stopped: " + " | ".join(problems))


def render_document(
    title: str,
    sections: list[tuple[str, list[PackageRecord]]],
    extra_texts: list[tuple[str, str]] | None = None,
    disclosures: list[Disclosure] | None = None,
) -> str:
    all_records = [record for _, records in sections for record in records]
    parts = [
        f"# {title}",
        "",
        "This document identifies third-party software represented by the resolved dependency inventories for this distribution. "
        "Each component remains subject to its own license terms. No third-party license changes the licensing status of "
        "the Love Journal project's original code.",
        "",
        "Generated from committed dependency locks and locally available package metadata by "
        "`tools/generate_third_party_notices.py`.",
        "",
        *GENERATION_NOTE,
        "",
    ]
    if disclosures:
        parts.extend(["## Service and distribution boundaries", ""])
        for english, chinese in disclosures:
            parts.extend([english, "", chinese, ""])
    for section_title, records in sections:
        parts.extend([inventory_section(section_title, records), ""])
    parts.append(license_text_section(all_records, extra_texts))
    return "\n".join(parts)


def render_notice(
    counts: list[tuple[str, int]],
    component: str = "Love Journal",
    disclosures: list[Disclosure] | None = None,
) -> str:
    lines = [
        component,
        "",
        "This distribution includes third-party software. Copyright notices, license declarations,",
        "license sources, project sources, and available license texts are provided in THIRD_PARTY_LICENSES.md.",
        "",
        *GENERATION_NOTE,
        "",
        "Included resolved dependency inventories:",
    ]
    lines.extend(f"- {name}: {count} packages" for name, count in counts)
    lines.extend(
        [
            "",
            "The Love Journal project's original code is separate from these third-party works.",
            "This notice does not grant a license to that original code.",
        ]
    )
    if disclosures:
        lines.extend(["", "Service and distribution boundaries:"])
        for english, chinese in disclosures:
            lines.extend([english, chinese, ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate third-party notices from resolved dependency inventories.")
    parser.add_argument(
        "--python-wheel-directory",
        type=Path,
        help="Directory containing the complete, resolved Linux CPython 3.12 wheel set for server/requirements.lock.",
    )
    parser.add_argument(
        "--python-site-packages",
        type=Path,
        help="Exact site-packages directory matching server/requirements.lock.",
    )
    parser.add_argument(
        "--write-python-lock",
        action="store_true",
        help="Write server/requirements.lock from --python-wheel-directory before generating notices.",
    )
    parser.add_argument(
        "--refresh-android-lock",
        action="store_true",
        help="Write Android/third_party_dependencies.json from the release Gradle artifact inventory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server_project = ROOT / "server"
    android_project = ROOT / "Android"
    if args.write_python_lock:
        if args.python_wheel_directory is None:
            raise RuntimeError("--write-python-lock requires --python-wheel-directory")
        write_python_lock(server_project, wheel_distributions(args.python_wheel_directory))
    if args.refresh_android_lock:
        refresh_android_lock(android_project)

    web = npm_records(ROOT / "web")
    netease = npm_records(ROOT / "netease-api")
    server = python_records(
        server_project,
        site_packages=args.python_site_packages,
        wheel_directory=args.python_wheel_directory,
    )
    android = android_records(android_project)
    all_records = android + web + netease + server
    apache_text = find_apache_license(all_records)
    android_disclosure = android_sdk_disclosure(android)
    root_disclosures = [NETEASE_SERVICE_DISCLOSURE]
    if android_disclosure is not None:
        root_disclosures.append(android_disclosure)

    sections = [
        ("Android client release runtime", android),
        ("Web client", web),
        ("Python server", server),
        ("NetEase API helper", netease),
    ]
    validate_license_inventory(sections)
    counts = [(name, len(records)) for name, records in sections]
    write_text(ROOT / "NOTICE", render_notice(counts, disclosures=root_disclosures))
    android_apache_extra = []
    if any("Apache-2.0" in record.license_name for record in android):
        android_apache_extra.append(("Android dependencies declared as Apache-2.0", apache_text))
    write_text(
        ROOT / "THIRD_PARTY_LICENSES.md",
        render_document(
            "Third-Party Software Notices",
            sections,
            android_apache_extra,
            disclosures=root_disclosures,
        ),
    )

    component_outputs = [
        (ROOT / "web" / "public", "Love Journal Web Client", [("Web client", web)], [], []),
        (ROOT / "server", "Love Journal Python Server", [("Python server", server)], [], []),
        (
            ROOT / "netease-api",
            "Love Journal NetEase API Helper",
            [("NetEase API helper", netease)],
            [],
            [NETEASE_SERVICE_DISCLOSURE],
        ),
    ]
    for directory, component, component_sections, extra_texts, component_disclosures in component_outputs:
        component_counts = [(name, len(records)) for name, records in component_sections]
        write_text(
            directory / "NOTICE",
            render_notice(component_counts, component, disclosures=component_disclosures),
        )
        write_text(
            directory / "THIRD_PARTY_LICENSES.md",
            render_document(
                f"{component} Third-Party Notices",
                component_sections,
                extra_texts,
                disclosures=component_disclosures,
            ),
        )

    android_directory = android_project / "app" / "src" / "main" / "res" / "raw"
    write_text(
        android_directory / "notice.txt",
        render_notice(
            [("Android client release runtime", len(android))],
            "Love Journal Android Client",
            disclosures=[android_disclosure] if android_disclosure is not None else [],
        ),
    )
    write_text(
        android_directory / "third_party_licenses.md",
        render_document(
            "Love Journal Android Client Third-Party Notices",
            [("Android client release runtime", android)],
            android_apache_extra,
            disclosures=[android_disclosure] if android_disclosure is not None else [],
        ),
    )

    unblock = next((record for record in netease if record.name == "@unblockneteasemusic/server"), None)
    if unblock is None or "LGPL-3.0" not in unblock.license_name or not unblock.source:
        raise RuntimeError("LGPL dependency attribution is incomplete")

    print("Generated notices:")
    for name, count in counts:
        print(f"- {name}: {count}")
    print(f"- LGPL source: {unblock.source}")


if __name__ == "__main__":
    main()
