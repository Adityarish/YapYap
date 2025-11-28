import re
from dataclasses import dataclass
from typing import Optional

from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline


MODEL_NAME = "oliverguhr/fullstop-punctuation-multilang-large"


@dataclass
class PunctuationRestorer:
    model_name: str = MODEL_NAME
    _pipeline: Optional[pipeline] = None

    def _load(self) -> pipeline:
        if self._pipeline is None:
            tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            model = AutoModelForTokenClassification.from_pretrained(self.model_name)
            self._pipeline = pipeline(
                "token-classification",
                model=model,
                tokenizer=tokenizer,
                aggregation_strategy="simple",
            )
        return self._pipeline

    def restore(self, text: str) -> str:
        if not text or not text.strip():
            return ""

        punct_pipeline = self._load()
        predictions = punct_pipeline(text)

        output_text = ""
        last_idx = 0
        predictions = sorted(predictions, key=lambda x: x["start"])

        for pred in predictions:
            start = pred["start"]
            end = pred["end"]
            label = pred["entity_group"]

            output_text += text[last_idx:end]
            if label != "0":
                output_text += label
            last_idx = end

        output_text += text[last_idx:]
        return output_text


def auto_format(text: str) -> str:
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"(,\s*){2,}", ", ", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"([.!?])\s*,", r"\1", text)
    sentences = re.split(r"([.!?])", text)
    formatted = ""

    for i in range(0, len(sentences) - 1, 2):
        s = sentences[i].strip()
        p = sentences[i + 1]
        if s:
            s = s[0].upper() + s[1:]
            formatted += s + p + " "

    if len(sentences) % 2 != 0:
        last = sentences[-1].strip()
        if last:
            formatted += last[0].upper() + last[1:]

    return formatted.strip()


class TextFormatter:
    def __init__(self, restorer: Optional[PunctuationRestorer] = None) -> None:
        self.restorer = restorer or PunctuationRestorer()

    def format(self, text: str, *, restore_punct: bool = True) -> str:
        processed = text
        if restore_punct:
            processed = self.restorer.restore(text)
        return auto_format(processed)


PUNCTUATION_RESTORER = PunctuationRestorer()
TEXT_FORMATTER = TextFormatter(PUNCTUATION_RESTORER)


def restore_punctuation(text: str) -> str:
    return PUNCTUATION_RESTORER.restore(text)


def format_text(text: str, *, restore_punct: bool = True) -> str:
    return TEXT_FORMATTER.format(text, restore_punct=restore_punct)