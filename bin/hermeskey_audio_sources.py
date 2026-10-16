"""Parse PipeWire/PulseAudio sources; discovery never opens the microphone."""
import json
from dataclasses import dataclass


class SourceDiscoveryError(ValueError):
    pass


@dataclass(frozen=True)
class AudioSource:
    name: str
    description: str
    is_monitor: bool


def parse_json_sources(data: str) -> list[AudioSource]:
    try:
        entries = json.loads(data)
    except (ValueError, TypeError) as exc:
        raise SourceDiscoveryError("Invalid source JSON") from exc
    if not isinstance(entries, list):
        raise SourceDiscoveryError("Invalid source list")
    sources = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry["name"]:
            continue
        name = entry["name"]
        properties = entry.get("properties") or {}
        if not isinstance(properties, dict):
            properties = {}
        description = entry.get("description")
        if not isinstance(description, str) or not description.strip():
            description = properties.get("device.description") or name
        if not isinstance(description, str):
            description = name
        monitor = (
            name.endswith(".monitor")
            or bool(entry.get("monitor_source"))
            or properties.get("media.class") == "Audio/Sink"
        )
        sources.append(AudioSource(name, " ".join(description.split())[:160], monitor))
    return sources


def parse_short_sources(data: str) -> list[AudioSource]:
    sources = []
    for line in data.splitlines():
        columns = line.split("\t")
        if len(columns) < 2:
            continue
        name = columns[1].strip()
        if name:
            sources.append(AudioSource(name, name, name.endswith(".monitor")))
    return sources
