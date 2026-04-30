"""Offline tests for structured AI output parsing."""

import json
import unittest

from pydantic import ValidationError

from core.schemas import ReelAnalysis


class TestReelAnalysisSchema(unittest.TestCase):
    def test_parse_valid_payload(self) -> None:
        payload = {
            "topic": "Fitness progress content",
            "hook": "Fast zoom on face with bold on-screen text",
            "why_it_worked": "Strong contrast format and concise pacing drive retention.",
            "creator_script": "0-1s hook, 1-8s contrast reveal, 8-12s CTA.",
        }
        raw = json.dumps(payload)
        obj = ReelAnalysis.model_validate_json(raw)
        self.assertEqual(obj.topic, payload["topic"])
        self.assertEqual(obj.hook, payload["hook"])

    def test_rejects_missing_field(self) -> None:
        raw = json.dumps({"topic": "x", "hook": "y", "why_it_worked": "z"})
        with self.assertRaises(ValidationError):
            ReelAnalysis.model_validate_json(raw)


if __name__ == "__main__":
    unittest.main()
