from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict

from .components.fillers_removal import SPEECH_CLEANER
from .components.format import format_text
from .components.grammar import correct_grammar
from .components.tone import tone_transform


def _round_ms(value: float) -> float:
    return round(value * 1000, 3)


@dataclass
class ChunkPreprocessor:
    """Pipeline that normalizes Whisper chunks for downstream consumption."""

    tone_mode: str = "neutral"
    restore_punctuation: bool = True
    apply_grammar: bool = True
    use_seq2seq_cleaner: bool = False
    remove_repetition: bool = True

    def __post_init__(self) -> None:
        self.tone_mode = (self.tone_mode or "neutral").lower().strip()

    def __call__(self, text: str) -> Dict[str, Any]:
        return self.process(text)

    def process(self, text: str) -> Dict[str, Any]:
        timings: Dict[str, float] = {}

        cleaned = SPEECH_CLEANER.clean(
            text,
            use_model=self.use_seq2seq_cleaner,
            mode=self.tone_mode if self.use_seq2seq_cleaner else "neutral",
            remove_repetition=self.remove_repetition,
            with_timings=True,
        )

        timings.update(cleaned["timings_ms"])
        after_cleaning = cleaned["after_repetition"]

        processed_text = after_cleaning

        if self.apply_grammar:
            t0 = time.time()
            processed_text = correct_grammar(processed_text)
            timings["grammar_ms"] = _round_ms(time.time() - t0)
        else:
            timings["grammar_ms"] = 0.0

        tone_text = processed_text
        if self.tone_mode and self.tone_mode not in {"neutral", ""}:
            t1 = time.time()
            tone_text = tone_transform(processed_text, self.tone_mode)
            timings["tone_ms"] = _round_ms(time.time() - t1)
        else:
            timings["tone_ms"] = 0.0

        t2 = time.time()
        final_text = format_text(tone_text, restore_punct=self.restore_punctuation)
        timings["format_ms"] = _round_ms(time.time() - t2)

        return {
            "original": text,
            "after_fillers": cleaned["after_fillers"],
            "after_repetition": after_cleaning,
            "after_grammar": processed_text,
            "after_tone": tone_text,
            "final": final_text,
            "timings_ms": timings,
        }
