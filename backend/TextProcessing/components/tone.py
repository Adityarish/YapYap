import re
from dataclasses import dataclass
from typing import Callable, Dict


FORMAL_MAP = {
    r"\bhey\b": "hello",
    r"\bhi\b": "hello",
    r"\bok\b": "okay",
    r"\bokay\b": "alright",
    r"\bkind of\b": "somewhat",
    r"\bkinda\b": "somewhat",
    r"\bpretty\b": "quite",
    r"\breally\b": "significantly",
    r"\bgonna\b": "going to",
    r"\bwanna\b": "want to",
}

CASUAL_MAP = {
    r"\bhello\b": "hey",
    r"\balright\b": "ok",
    r"\bimportant\b": "kinda important",
    r"\bsignificantly\b": "really",
    r"\bquite\b": "pretty",
    r"\bdo not\b": "don't",
    r"\bcannot\b": "can't",
}

NEUTRAL_REMOVE = [
    r"\breally\b",
    r"\bpretty\b",
    r"\bvery\b",
    r"\bextremely\b",
    r"\bsomewhat\b",
    r"\bhighly\b",
]


def _apply_map(text: str, mapping: Dict[str, str]) -> str:
    for src, tgt in mapping.items():
        text = re.sub(src, tgt, text, flags=re.IGNORECASE)
    return text


def _remove_words(text: str, word_list) -> str:
    for w in word_list:
        text = re.sub(w, "", text, flags=re.IGNORECASE)
    return " ".join(text.split())


def _make_concise(text: str) -> str:
    text = re.sub(r"\bi think\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bi guess\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bkind of\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsort of\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmaybe\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bit's\b", "it is", text, flags=re.IGNORECASE)
    text = " ".join(text.split())
    if "," in text:
        text = text.split(",")[0]
    text = text.strip()
    return text.capitalize() + "." if text else text


@dataclass
class ToneTransformer:
    modes: Dict[str, Callable[[str], str]]

    def __call__(self, text: str, mode: str) -> str:
        return self.transform(text, mode=mode)

    def transform(self, text: str, mode: str) -> str:
        normalized = " ".join(text.split())
        key = mode.lower().strip()
        func = self.modes.get(key)
        if func is None:
            return normalized
        return func(normalized)


TONE_TRANSFORMER = ToneTransformer(
    modes={
        "formal": lambda txt: _apply_map(txt, FORMAL_MAP),
        "casual": lambda txt: _apply_map(txt, CASUAL_MAP),
        "neutral": lambda txt: _remove_words(txt, NEUTRAL_REMOVE),
        "concise": _make_concise,
    }
)


def tone_transform(text: str, mode: str) -> str:
    return TONE_TRANSFORMER.transform(text, mode=mode)