from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer


MODEL_NAME = "prithivida/grammar_error_correcter_v1"


@dataclass
class GrammarCorrector:
    tokenizer: T5Tokenizer
    model: T5ForConditionalGeneration

    @classmethod
    def load(cls, model_name: str = MODEL_NAME) -> "GrammarCorrector":
        tokenizer = T5Tokenizer.from_pretrained(model_name)
        model = T5ForConditionalGeneration.from_pretrained(model_name)
        model.eval()
        return cls(tokenizer=tokenizer, model=model)

    def correct(self, text: str) -> str:
        input_text = "gec: " + text
        inputs = self.tokenizer.encode(
            input_text,
            return_tensors="pt",
            max_length=256,
            truncation=True,
        )

        with torch.no_grad():
            outputs = self.model.generate(
                inputs,
                max_length=256,
                num_beams=4,
                early_stopping=True,
            )

        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def batch_correct(self, sentences: Iterable[str]) -> List[str]:
        return [self.correct(sentence) for sentence in sentences]


GRAMMAR = GrammarCorrector.load()


def correct_grammar(text: str) -> str:
    return GRAMMAR.correct(text)


def batch_correct(sentences: Iterable[str]) -> List[str]:
    return GRAMMAR.batch_correct(sentences)