"""Remembers vocabulary already shown so words do not repeat."""

import json
import logging
import re

import config

log = logging.getLogger(__name__)
_ARTICLE = re.compile(r"^(der|die|das)\s+", re.IGNORECASE)


def _key(word: str) -> str:
    return _ARTICLE.sub("", word.strip()).lower()


class History:
    def __init__(self):
        self.path = config.data_dir() / "history.json"
        self.words = self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [w for w in data if isinstance(w, str)]
        except FileNotFoundError:
            return []
        except Exception:
            log.exception("Could not read history; starting empty.")
            return []

    def has(self, word: str) -> bool:
        k = _key(word)
        return any(_key(w) == k for w in self.words)

    def recent(self, n: int):
        return self.words[-n:]

    def add(self, word: str):
        self.words.append(word.strip())
        self.words = self.words[-config.HISTORY_MAX:]
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.words, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:
            log.exception("Could not save history.")
