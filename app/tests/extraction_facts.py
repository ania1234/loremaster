"""Facts that must survive extraction from data/Reincarnated as the Unlovable Villainess.pdf, with their context intact.

Each entry: (label, page, [fragments that must appear close together]).
The point is proximity -- a fragment alone on the page proves nothing,
because the chunker will separate it from its meaning.
"""

WINDOW = 400          # characters; a rough proxy for "same chunk"

FACTS = [
    ("heart meter floor", 1, ["-1", "Hatred, Disgust, Loathing"]),
    ("game length",       2, ["30 days", "avoid"]),
    ("plot twist 19",     5, ["19", "developer", "talking to you in your sleep"]),
    ("who is 5",          5, ["1.", "Loved", "2.", "Hated"]),
    ("time travel",       8, ["time travel", "Black threads"]),
    ("tsundere",          5, [ "1.", "Tsundere"]),
    ("column break", 8, ["10.", "11."]),
]