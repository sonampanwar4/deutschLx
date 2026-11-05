"""Talks to Ollama: creates vocabulary and checks the learner's sentence."""

import json
import logging
import random
import re

from ollama import Client

import config

log = logging.getLogger(__name__)

VOCAB_SCHEMA = {
    "type": "object",
    "properties": {
        "word": {"type": "string"},
        "plural": {"type": "string"},
        "meaning": {"type": "string"},
        "sentence": {"type": "string"},
        "translation": {"type": "string"},
        "verbs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "infinitive": {"type": "string"},
                    "preterite": {"type": "string"},
                    "participle": {"type": "string"},
                },
                "required": ["infinitive", "preterite", "participle"],
            },
        },
    },
    "required": ["word", "plural", "meaning", "sentence", "translation", "verbs"],
}

CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "is_correct": {"type": "boolean"},
        "corrected_sentence": {"type": "string"},
    },
    "required": ["is_correct", "corrected_sentence"],
}

VOCAB_SYSTEM = """You are a German vocabulary teacher for an English-speaking learner.
Create exactly ONE German noun entry as JSON with these keys:
- word: the noun with its singular article, e.g. "die Entscheidung"
- plural: the plural with article, e.g. "die Entscheidungen"
- meaning: short English meaning
- sentence: one natural German sentence (level {level}) that uses the noun
- translation: accurate English translation of that sentence
- verbs: EVERY verb that occurs in the German sentence (include modal and auxiliary
  verbs, each only once) with:
  infinitive; preterite (Präteritum, 3rd person singular, e.g. "las");
  auxiliary: "haben" or "sein" - the auxiliary this verb uses in the Perfekt
  (e.g. lesen -> haben, gehen -> sein, aufstehen -> sein, müssen -> haben);
  participle: the bare Partizip II only (e.g. "gelesen", "gegangen").
Use correct standard German. Return JSON only."""

CHECK_SYSTEM = """You are a fair but careful German teacher checking ONE sentence written
by a learner. Check grammar, word order, verb conjugation, cases, articles, noun gender,
spelling and the capitalisation of nouns. Ignore a missing full stop or question mark.
The sentence may say anything; it does not have to copy the example sentence.
If the sentence is correct and natural: is_correct = true and corrected_sentence is the
learner's sentence unchanged.
Otherwise: is_correct = false and corrected_sentence is ONE corrected German sentence that
keeps the learner's meaning and changes as little as possible. If the learner wrote in
English or another language, give the German sentence they meant.
Return JSON only. Do not explain."""


def _parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _norm(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence.strip()).rstrip(".!? ").strip()


class OllamaEngine:
    def __init__(self):
        self.client = Client(host=config.OLLAMA_HOST,
                             timeout=config.REQUEST_TIMEOUT_SECONDS)

    def _chat(self, system, user, schema, think, temperature, max_tokens):
        response = self.client.chat(
            model=config.MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            format=schema,
            think=think,
            keep_alive=config.KEEP_ALIVE,
            options={"temperature": temperature, "num_predict": max_tokens,
                     "num_ctx": 4096},
        )
        return _parse_json(response["message"]["content"])

    # ---- vocabulary -------------------------------------------------------
    def generate_entry(self, history=None):
        entry = None
        for attempt in range(3):
            avoid = history.recent(config.HISTORY_WORDS_IN_PROMPT) if history else []
            user = (
                f"Theme: {random.choice(config.THEMES)}.\n"
                + (f"Do NOT use these nouns: {', '.join(avoid)}.\n" if avoid else "")
                + "Create the entry now."
            )
            data = self._chat(
                VOCAB_SYSTEM.format(level=config.LEVEL), user, VOCAB_SCHEMA,
                config.THINK_WHEN_GENERATING, 0.8, 600,
            )
            entry = self._clean_entry(data)
            if not history or not history.has(entry["word"]):
                return entry
            log.info("Duplicate word %r, retrying (%d)", entry["word"], attempt + 1)
        return entry  # three duplicates in a row: accept rather than fail

    @staticmethod
    def _clean_entry(data):
        entry = {}
        for key in ("word", "plural", "meaning", "sentence", "translation"):
            value = str(data.get(key, "")).strip()
            if not value:
                raise ValueError(f"The model returned an empty '{key}'.")
            entry[key] = value
        entry["word"] = entry["word"][0].upper() + entry["word"][1:]
        verbs, seen = [], set()
        for v in data.get("verbs") or []:
            if not isinstance(v, dict):
                continue
            inf = str(v.get("infinitive", "")).strip()
            if not inf or inf.lower() in seen:
                continue
            seen.add(inf.lower())
            verbs.append((inf, str(v.get("preterite", "")).strip(),
                          str(v.get("participle", "")).strip()))
        entry["verbs"] = verbs[:6]
        return entry

    # ---- sentence check ---------------------------------------------------
    def check_sentence(self, entry, sentence):
        """Return {'is_correct': bool, 'corrected': str}."""
        user = (
            f"Vocabulary of the day: {entry['word']}\n"
            f"Example sentence: {entry['sentence']}\n"
            f"Learner's sentence: {sentence}"
        )
        data = self._chat(CHECK_SYSTEM, user, CHECK_SCHEMA,
                          config.THINK_WHEN_CHECKING, 0.1, 250)
        corrected = str(data.get("corrected_sentence", "")).strip()
        is_correct = bool(data.get("is_correct"))
        if not is_correct and _norm(corrected) == _norm(sentence):
            is_correct = True            # the model "corrected" nothing
        if not is_correct and not corrected:
            raise ValueError("The model did not return a corrected sentence.")
        return {"is_correct": is_correct, "corrected": corrected}
