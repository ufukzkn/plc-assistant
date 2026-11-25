"""Local Turkish question suggestions backed by a small curated corpus."""
import re
import unicodedata
from collections import Counter
from functools import lru_cache

from query import ADDRESS_PATTERN

CORPUS = (
    ("çalışıyor mu?", ("aktif mi", "açık mı", "devrede mi", "çalışma durumu")),
    ("neden çıkış vermiyor?", ("neden çalışmıyor", "çıkış yok", "sebep")),
    ("giriş koşulu nedir?", ("koşul", "hangi şart", "giriş")),
    ("nerede kullanılıyor?", ("hangi devre", "hangi çıkış", "kullanım")),
    ("reset koşulu nedir?", ("reset", "reset yolu")),
    ("zamanlayıcı tamamlandı mı?", ("süre", "kaç saniye", "timer")),
    ("hangi alarmlar var?", ("alarm", "alarmları listele", "aktif alarmlar")),
)
ALARM_QUESTION = CORPUS[-1][0]


def normalize_text(text):
    joined = unicodedata.normalize("NFKD", text.lower().replace("ı", "i"))
    return "".join(char for char in joined if not unicodedata.combining(char))


def words(text):
    return tuple(re.findall(r"[a-z0-9]+", normalize_text(text)))


def is_status_question(text):
    return words(text) in STATUS_PHRASES


@lru_cache(maxsize=512)
def one_typo(left, right):
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) > len(right):
        left, right = right, left
    for index, (a, b) in enumerate(zip(left, right)):
        if a == b:
            continue
        if len(left) < len(right):
            return left[index:] == right[index + 1:]
        return (left[index + 1:] == right[index + 1:]
                or (left[index:index + 2] == right[index:index + 2][::-1]
                    and left[index + 2:] == right[index + 2:]))
    return True


def match_score(query, candidate):
    if len(query) > len(candidate):
        return 0
    score = 0
    for index, (entered, expected) in enumerate(zip(query, candidate)):
        if entered == expected:
            score += 4
        elif index == len(query) - 1 and expected.startswith(entered):
            score += 3
        elif len(entered) >= 4 and one_typo(entered, expected):
            score += 1
        else:
            return 0
    return score + (2 if len(query) == len(candidate) else 0)


PHRASES = tuple((title, tuple(map(words, (title, *aliases)))) for title, aliases in CORPUS)
STATUS_PHRASES = {*PHRASES[0][1], words("durumu ne")}


def suggest(text, rows=(), labels=None, current=None, limit=4):
    text = text.strip()
    if not 2 <= len(text) <= 160:
        return []
    matches = list(ADDRESS_PATTERN.finditer(text))
    if len(matches) > 1:
        return []
    address = matches[0].group().strip().upper() if matches else None
    source = (text[:matches[0].start()] + " " + text[matches[0].end():]) if matches else text
    query = words(source)
    options = []
    for title, phrases in PHRASES:
        if title == ALARM_QUESTION and address:
            continue
        if query:
            score = max(match_score(query, candidate) + (8 if query == candidate else 0)
                        for candidate in phrases)
        else:
            score = 1
        if score:
            target = address or current
            value = f"{target} {title}" if target and title != ALARM_QUESTION else title
            options.append((score, value))

    if not address:
        eligible = Counter(row[0] for row in rows)
        labels = labels or {}
        compact = "".join(query)
        for target, count in eligible.items():
            if count != 1:
                continue
            label = words(labels.get(target, ""))
            address_prefix = compact and target.lower().replace(".", "").startswith(compact)
            label_score = max((match_score(query, label[i:]) for i in range(len(label))), default=0)
            if address_prefix or label_score:
                options.append((6 + label_score, f"{target} {CORPUS[0][0]}"))

    ranked = sorted(options, key=lambda item: -item[0])
    return list(dict.fromkeys(value for _, value in ranked if value.casefold() != text.casefold()))[:limit]
