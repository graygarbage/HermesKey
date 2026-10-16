"""Microphone discovery parses metadata only; no device is opened."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from hermeskey_audio_sources import SourceDiscoveryError, parse_json_sources, parse_short_sources


class AudioSourceTests(unittest.TestCase):
    def test_json_descriptions_and_monitor_detection(self):
        payload = [
            {"name": "alsa_input.usb-Mic-00", "description": "USB Microphone", "monitor_source": "",
             "properties": {"media.class": "Audio/Source"}},
            {"name": "alsa_output.speakers.monitor", "description": "Monitor of Speakers",
             "monitor_source": "alsa_output.speakers", "properties": {"media.class": "Audio/Sink"}},
            {"name": "virtual.source", "properties": {"device.description": "Virtual Mic"}},
        ]
        sources = parse_json_sources(json.dumps(payload))
        self.assertEqual([s.name for s in sources], ["alsa_input.usb-Mic-00", "alsa_output.speakers.monitor", "virtual.source"])
        self.assertEqual([s.description for s in sources], ["USB Microphone", "Monitor of Speakers", "Virtual Mic"])
        self.assertEqual([s.is_monitor for s in sources], [False, True, False])

    def test_text_fallback_uses_source_name_not_index(self):
        sources = parse_short_sources("42\talsa_input.usb-Mic-00\tPipeWire\tRUNNING\n"
                                      "43\talsa_output.monitor\tPipeWire\tSUSPENDED\n")
        self.assertEqual(sources[0].name, "alsa_input.usb-Mic-00")
        self.assertTrue(sources[1].is_monitor)

    def test_bad_json_reports_error(self):
        with self.assertRaises(SourceDiscoveryError):
            parse_json_sources("not json")
        with self.assertRaises(SourceDiscoveryError):
            parse_json_sources('{}')


if __name__ == "__main__":
    unittest.main()
