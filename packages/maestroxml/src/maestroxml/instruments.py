from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata


@dataclass(frozen=True)
class InstrumentChoice:
    label: str
    aliases: tuple[str, ...]
    bridge_instrument_id: str | None = None
    musicxml_id: str | None = None


COMMON_INSTRUMENT_CHOICES: tuple[InstrumentChoice, ...] = (
    InstrumentChoice(
        label="Grand Piano",
        aliases=("piano", "grand piano", "upright piano", "keyboard"),
        bridge_instrument_id="piano",
    ),
    InstrumentChoice(
        label="Horn in F",
        aliases=("horn", "french horn", "horn in f", "f horn", "hn"),
        musicxml_id="brass.french-horn",
    ),
    InstrumentChoice(
        label="B-flat Trumpet",
        aliases=(
            "trumpet",
            "bb trumpet",
            "b flat trumpet",
            "trumpet in bb",
            "cornet",
            "piccolo trumpet",
            "flugelhorn",
            "baroque trumpet",
            "pocket trumpet",
        ),
        musicxml_id="brass.trumpet.bflat",
    ),
    InstrumentChoice(
        label="Trombone",
        aliases=("trombone", "tenor trombone", "tbn", "sackbut"),
        musicxml_id="brass.trombone",
    ),
    InstrumentChoice(
        label="B-flat Clarinet",
        aliases=(
            "clarinet",
            "bb clarinet",
            "b flat clarinet",
            "clarinet in bb",
            "a clarinet",
            "eb clarinet",
            "e flat clarinet",
        ),
        musicxml_id="wind.reed.clarinet.bflat",
    ),
    InstrumentChoice(
        label="Bass Clarinet",
        aliases=(
            "bass clarinet",
            "contra alto clarinet",
            "contrabass clarinet",
            "basset horn",
            "basset clarinet",
        ),
        musicxml_id="wind.reed.clarinet.bass",
    ),
    InstrumentChoice(
        label="Oboe",
        aliases=("oboe", "baroque oboe", "oboe d'amore", "oboe da caccia"),
        bridge_instrument_id="oboe",
    ),
    InstrumentChoice(
        label="English Horn",
        aliases=("english horn", "cor anglais"),
        bridge_instrument_id="english-horn",
    ),
    InstrumentChoice(
        label="Bassoon",
        aliases=("bassoon", "contrabassoon"),
        bridge_instrument_id="bassoon",
    ),
    InstrumentChoice(
        label="Piccolo",
        aliases=("piccolo",),
        bridge_instrument_id="piccolo",
    ),
    InstrumentChoice(
        label="Alto Saxophone",
        aliases=("alto sax", "alto saxophone", "saxophone", "sax"),
        musicxml_id="wind.reed.saxophone.alto",
    ),
    InstrumentChoice(
        label="Tenor Saxophone",
        aliases=("tenor sax", "tenor saxophone"),
        musicxml_id="wind.reed.saxophone.tenor",
    ),
    InstrumentChoice(
        label="Baritone Saxophone",
        aliases=("baritone sax", "baritone saxophone", "bari sax"),
        musicxml_id="wind.reed.saxophone.baritone",
    ),
    InstrumentChoice(
        label="Soprano Saxophone",
        aliases=("soprano sax", "soprano saxophone"),
        bridge_instrument_id="soprano-saxophone",
    ),
    InstrumentChoice(
        label="Tuba",
        aliases=("tuba", "sousaphone", "wagner tuba", "ophicleide", "helicon"),
        musicxml_id="brass.tuba",
    ),
    InstrumentChoice(
        label="Euphonium",
        aliases=("euphonium", "baritone horn", "baritone"),
        bridge_instrument_id="euphonium",
    ),
    InstrumentChoice(
        label="Double Bass",
        aliases=("double bass", "contrabass", "string bass", "acoustic bass"),
        bridge_instrument_id="contrabass",
    ),
    InstrumentChoice(
        label="Drumset",
        aliases=("drumset", "drum set", "drums", "kit", "percussion set"),
        bridge_instrument_id="drumset",
    ),
    InstrumentChoice(
        label="Timpani",
        aliases=("timpani", "kettledrums", "kettle drums"),
        bridge_instrument_id="timpani",
    ),
    InstrumentChoice(
        label="Marimba",
        aliases=("marimba",),
        bridge_instrument_id="marimba",
    ),
    InstrumentChoice(
        label="Vibraphone",
        aliases=("vibraphone", "vibes"),
        bridge_instrument_id="vibraphone",
    ),
    InstrumentChoice(
        label="Xylophone",
        aliases=("xylophone",),
        bridge_instrument_id="xylophone",
    ),
    InstrumentChoice(
        label="Glockenspiel",
        aliases=("glockenspiel", "bells"),
        bridge_instrument_id="glockenspiel",
    ),
    InstrumentChoice(
        label="Organ",
        aliases=("organ", "pipe organ", "hammond organ"),
        bridge_instrument_id="organ",
    ),
    InstrumentChoice(
        label="Accordion",
        aliases=("accordion", "bandoneon"),
        bridge_instrument_id="accordion",
    ),
    InstrumentChoice(
        label="Harp",
        aliases=("harp",),
        bridge_instrument_id="harp",
    ),
)


def _normalize_instrument_text(value: str) -> str:
    cleaned = value.replace("♭", "b").replace("♯", "#").replace("&", " and ")
    cleaned = unicodedata.normalize("NFKD", cleaned)
    cleaned = "".join(character for character in cleaned if not unicodedata.combining(character))
    cleaned = cleaned.lower()
    cleaned = cleaned.replace("b-flat", "bb").replace("b flat", "bb")
    cleaned = cleaned.replace("e-flat", "eb").replace("e flat", "eb")
    cleaned = cleaned.replace("a-flat", "ab").replace("a flat", "ab")
    cleaned = cleaned.replace("d-flat", "db").replace("d flat", "db")
    cleaned = cleaned.replace("g-flat", "gb").replace("g flat", "gb")
    cleaned = cleaned.replace("c-flat", "cb").replace("c flat", "cb")
    cleaned = cleaned.replace("f-sharp", "f#").replace("f sharp", "f#")
    cleaned = cleaned.replace("c-sharp", "c#").replace("c sharp", "c#")
    cleaned = re.sub(r"[^a-z0-9#+]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _candidate_strings(choice: InstrumentChoice) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            _normalize_instrument_text(item)
            for item in (choice.label, *choice.aliases)
            if item
        )
    )


def _score_candidate(query: str, candidate_strings: tuple[str, ...]) -> float:
    if not query:
        return 0.0

    best = 0.0
    query_parts = query.split()
    query_tokens = set(query.split())
    for candidate in candidate_strings:
        if not candidate:
            continue
        if query == candidate:
            return 1.0
        if query in candidate or candidate in query:
            candidate_parts = candidate.split()
            if len(candidate_parts) > 1 or len(query_parts) == 1:
                best = max(best, 0.97)
            else:
                best = max(best, 0.79)
            continue

        candidate_tokens = set(candidate.split())
        overlap = (
            len(query_tokens & candidate_tokens) / len(query_tokens | candidate_tokens)
            if query_tokens or candidate_tokens
            else 0.0
        )
        ratio = SequenceMatcher(None, query, candidate).ratio()
        prefix_bonus = 0.08 if query_parts and query_parts[0] in candidate_tokens else 0.0
        best = max(best, ratio * 0.68 + overlap * 0.32 + prefix_bonus)
    return min(best, 0.999)


def _instrument_names_path() -> Path:
    return Path(__file__).with_name("musescore_instrument_names.json")


@lru_cache(maxsize=1)
def load_full_musescore_instrument_names() -> tuple[str, ...]:
    path = _instrument_names_path()
    names = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(names, list):
        return ()
    return tuple(name for name in names if isinstance(name, str) and name.strip())


def resolve_instrument_choice(
    requested_name: str,
) -> InstrumentChoice | None:
    query = _normalize_instrument_text(requested_name)
    if not query:
        return None

    common_match, common_score = _match_common_choice(query)
    if common_match is not None and common_score >= 0.94:
        return common_match

    full_name, full_score = _match_full_name(query)
    if full_name is not None and full_score >= 0.86:
        return InstrumentChoice(label=full_name, aliases=())

    if common_match is not None and common_score >= 0.64:
        return common_match

    if full_name is not None and full_score >= 0.74:
        return InstrumentChoice(label=full_name, aliases=())

    return None


def _match_common_choice(query: str) -> tuple[InstrumentChoice | None, float]:
    best_choice: InstrumentChoice | None = None
    best_score = 0.0
    for choice in COMMON_INSTRUMENT_CHOICES:
        score = _score_candidate(query, _candidate_strings(choice))
        if score > best_score:
            best_choice = choice
            best_score = score
    return best_choice, best_score


def _match_full_name(query: str) -> tuple[str | None, float]:
    best_name = ""
    best_score = 0.0
    for name in load_full_musescore_instrument_names():
        normalized_name = _normalize_instrument_text(name)
        score = _score_candidate(query, (normalized_name,))
        if score > best_score:
            best_name = name
            best_score = score
    if not best_name:
        return None, 0.0
    return best_name, best_score
