import re
import time
from typing import Any, Dict, Optional

from transformers import pipeline


SEQ2SEQ_MODEL_NAME = "t5-small"

# Fillers list (extend if needed)
FILLERS = {
    "um", "umm", "uh", "uhh", "ah", "erm", "mm", "hmm",
    "like", "you know", "i mean", "sort of", "kind of",
    "right", "okay", "ok", "basically", "actually", "so", "well"
}

HESITATION_RE = re.compile(
    r"\b(" + r"|".join(re.escape(x) for x in {"um", "uh", "umm", "uhh", "hmm", "erm"}) + r")\b",
    flags=re.I,
)


class SpeechCleaner:
    """Utility that removes fillers/repetitions and (optionally) runs seq2seq grammar cleanup."""

    def __init__(
        self,
        filler_words: Optional[set[str]] = None,
        hesitation_pattern: Optional[re.Pattern[str]] = None,
        seq2seq_model_name: str = SEQ2SEQ_MODEL_NAME,
    ) -> None:
        self.filler_words = frozenset(filler_words or FILLERS)
        self.hesitation_pattern = hesitation_pattern or HESITATION_RE
        self.seq2seq_model_name = seq2seq_model_name

        self._filler_pattern = re.compile(
            r"\b(" + r"|".join(re.escape(w) for w in self.filler_words) + r")\b",
            flags=re.I,
        )
        self._seq2seq_pipe = None

    # ----------------- core helpers -----------------
    def remove_fillers(self, text: str) -> str:
        """Remove known filler words and normalize whitespace."""
        t = re.sub(r"([,?.!;:])", r" \1 ", text)
        t = re.sub(r"\s+", " ", t).strip()
        t = self._filler_pattern.sub("", t)
        t = self.hesitation_pattern.sub("", t)
        t = re.sub(r"\s+([,?.!;:])", r"\1", t)
        t = re.sub(r"\s{2,}", " ", t).strip()
        return t

    def remove_repetitions(self, text: str, max_ngram: int = 4) -> str:
        tokens = text.split()
        n = len(tokens)
        if n <= 1:
            return text

        out_tokens: list[str] = []
        i = 0

        while i < n:
            found = False
            for g in range(min(max_ngram, n - i), 0, -1):
                if i + 2 * g <= n and tokens[i : i + g] == tokens[i + g : i + 2 * g]:
                    out_tokens.extend(tokens[i : i + g])
                    i += 2 * g
                    found = True
                    break
            if not found:
                out_tokens.append(tokens[i])
                i += 1

        return " ".join(out_tokens)

    # ----------------- optional seq2seq -----------------
    def _load_seq2seq(self):
        if self._seq2seq_pipe is None:
            self._seq2seq_pipe = pipeline(
                "text2text-generation", model=self.seq2seq_model_name, device=-1
            )
        return self._seq2seq_pipe

    def correct_grammar(self, text: str, mode: str = "neutral") -> str:
        pipe = self._load_seq2seq()
        prefix_map = {
            "neutral": "correct grammar: ",
            "formal": "paraphrase formal: ",
            "casual": "paraphrase casual: ",
            "concise": "paraphrase concise: ",
        }
        prompt = prefix_map.get(mode, "correct grammar: ") + text
        out = pipe(prompt, max_length=128, do_sample=False)[0]["generated_text"]
        return out.strip()

    # ----------------- public API -----------------
    def clean(
        self,
        text: str,
        *,
        use_model: bool = False,
        mode: str = "neutral",
        remove_repetition: bool = True,
        max_ngram: int = 4,
        with_timings: bool = False,
    ) -> Dict[str, Any] | str:
        timings: Dict[str, float] = {}

        t0 = time.time()
        after_fillers = self.remove_fillers(text)
        timings["fillers_ms"] = round((time.time() - t0) * 1000, 3)

        after_repetition = after_fillers
        if remove_repetition:
            t1 = time.time()
            after_repetition = self.remove_repetitions(after_fillers, max_ngram=max_ngram)
            timings["repetition_ms"] = round((time.time() - t1) * 1000, 3)
        else:
            timings["repetition_ms"] = 0.0

        final_text = after_repetition
        if use_model:
            t2 = time.time()
            final_text = self.correct_grammar(after_repetition, mode=mode)
            timings["model_ms"] = round((time.time() - t2) * 1000, 3)
        else:
            timings["model_ms"] = 0.0

        data: Dict[str, Any] = {
            "original": text,
            "after_fillers": after_fillers,
            "after_repetition": after_repetition,
            "final": final_text,
            "timings_ms": timings,
        }
        return data if with_timings else final_text

    def __call__(self, text: str, **kwargs: Any) -> Dict[str, Any] | str:
        return self.clean(text, **kwargs)


SPEECH_CLEANER = SpeechCleaner()


def remove_fillers(text: str) -> str:
    return SPEECH_CLEANER.remove_fillers(text)


def remove_repetitions(text: str, max_ngram: int = 4) -> str:
    return SPEECH_CLEANER.remove_repetitions(text, max_ngram=max_ngram)


def clean_speech(
    text: str,
    use_model: bool = False,
    mode: str = "neutral",
    remove_repetition: bool = True,
    max_ngram: int = 4,
    with_timings: bool = True,
) -> Dict[str, Any] | str:
    return SPEECH_CLEANER.clean(
        text,
        use_model=use_model,
        mode=mode,
        remove_repetition=remove_repetition,
        max_ngram=max_ngram,
        with_timings=with_timings,
    )


def load_seq2seq():
    return SPEECH_CLEANER._load_seq2seq()


def correct_grammar(text: str, mode: str = "neutral") -> str:
    return SPEECH_CLEANER.correct_grammar(text, mode=mode)
