"""Bounded local proposal provider. No network calls and no embedded credentials."""

from dataclasses import dataclass
from .generate import draft, add_options


@dataclass
class Limits:
    max_questions: int = 30
    max_attempts_per_question: int = 3
    max_output_characters: int = 160000
    max_model_calls: int = 0
    max_remote_retries: int = 0
    remote_timeout_seconds: int = 30
    estimated_remote_cost_limit_usd: float = 0.0


class FamilyProvider:
    """Executable baseline. The host AI authors and reviews the family designs."""

    name = "template"

    def propose(self, family, seed, kind, points):
        question = add_options(draft(family, seed, kind, points), seed + 1)
        question["generation"].update(
            mode="template", model_version=None, ai_dynamically_authored=False
        )
        return question
