#!/usr/bin/env python3
"""Build a public-only portfolio language chart from GitHub Linguist metadata."""
from collections import Counter
from html import escape
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree

OWNER = "Litju"
PORTFOLIO = (
    "DynamisRAG", "DynamisSignalBench", "Vibe-Product-Pal", "RecruiterPal",
    "football-performance-dynamics-bench", "powerlifting-state-research",
    "DynamisSimBench", "loaded-cmj-control", "loaded-cmj-system-identification",
    "DynamisETL", "ShoppingPal", "Sec-Scan-Monitor", "DynamisScience",
    "SportsAgentsLab-Public", "WorkoutPal-Public", "DynamisLM",
    "BioSynGenBenchmark", "PowerliftingStrengthDynamics", "PowerliftingSimulator",
)
START = "<!-- portfolio-language-stats:start -->"
END = "<!-- portfolio-language-stats:end -->"
COLORS = ("#72B7D4", "#57C0B2", "#D9A66C", "#A7A1E8", "#8FB9A4",
          "#E5A7A0", "#93A4B9", "#D8C582", "#91C7DB", "#B5A3CC")


def api(path):
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "Litju-public-portfolio-analytics"}
    url = "https://api.github.com" + path
    def get(auth):
        h = dict(headers)
        if auth:
            h["Authorization"] = "Bearer " + token
        with urlopen(Request(url, headers=h), timeout=30) as response:
            if response.geturl() != url:
                raise RuntimeError("Unexpected API redirect")
            return json.load(response)
    try:
        return get(bool(token))
    except HTTPError as exc:
        if token and exc.code in (403, 404):
            return get(False)  # public-only fallback
        raise


def public_portfolio(rows):
    allowed = {name.casefold() for name in PORTFOLIO}
    return sorted({
        row["name"] for row in rows
        if row.get("name", "").casefold() in allowed
        and row.get("owner", {}).get("login", "").casefold() == OWNER.casefold()
        and row.get("private") is False
        and row.get("fork") is False
        and row.get("archived") is False
    }, key=str.casefold)


def collect():
    rows = []
    for page in range(1, 101):
        batch = api(f"/users/{OWNER}/repos?type=owner&per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError("Expected public repository list")
        rows.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise RuntimeError("Repository pagination limit exceeded")
    names = public_portfolio(rows)
    if not names:
        raise RuntimeError("No public portfolio repositories found")
    data = {}
    for name in names:
        languages = api(f"/repos/{OWNER}/{quote(name, safe='')}/languages")
        if not isinstance(languages, dict) or any(
            not isinstance(k, str) or type(v) is not int or v < 0
            for k, v in languages.items()
        ):
            raise ValueError("Invalid language metadata")
        data[name] = languages
    return data


def aggregate(data):
    volume, presence = Counter(), Counter()
    for languages in data.values():
        for language, count in languages.items():
            if count:
                volume[language] += count
                presence[language] += 1
    if not volume:
        raise ValueError("No detected language bytes")
    ranked = sorted(volume, key=lambda lang: (-volume[lang], lang))
    return volume, presence, ranked


def render(data):
    volume, presence, ranked = aggregate(data)
    total = sum(volume.values())
    visible = ranked[:10]
    height = 174 + 43 * len(visible) + (30 if len(ranked) > 10 else 0)
    def t(x, y, label, size=14, color="#C7D3DE", anchor="start"):
        return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
                f'text-anchor="{anchor}">{escape(str(label))}</text>')
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Public portfolio language analytics</title>',
        '<desc id="desc">Ranked by GitHub Linguist bytes with repository coverage. Not a proficiency measure.</desc>',
        '<style>text{font-family:system-ui,-apple-system,Segoe UI,sans-serif;font-variant-numeric:tabular-nums}</style>',
        f'<rect x="1" y="1" width="958" height="{height-2}" rx="18" fill="#111820" stroke="#29333E"/>',
        t(28, 34, "PUBLIC PORTFOLIO  /  LANGUAGE ANALYTICS", 14, "#72B7D4"),
        t(28, 64, f"{len(data)} public projects  ·  {len(ranked)} detected languages", 19, "#EEF3F6"),
        '<rect x="28" y="82" width="904" height="13" rx="6" fill="#354451"/>',
    ]
    x = 28.0
    for i, lang in enumerate(visible):
        width = 904 * volume[lang] / total
        parts.append(f'<rect x="{x:.3f}" y="82" width="{width:.3f}" height="13" fill="{COLORS[i]}"/>')
        x += width
    parts.extend([t(28, 126, "LANGUAGE", 11, "#8E9AA7"),
                  t(250, 126, "SHARE OF DETECTED BYTES", 11, "#8E9AA7"),
                  t(932, 126, "REPOSITORIES", 11, "#8E9AA7", "end")])
    for i, lang in enumerate(visible):
        y = 151 + 43*i
        share = 100 * volume[lang] / total
        parts.extend([
            f'<circle cx="34" cy="{y-4}" r="5" fill="{COLORS[i]}"/>',
            t(48, y, lang, 14, "#EEF3F6"),
            f'<rect x="250" y="{y-12}" width="500" height="9" rx="4" fill="#29333E"/>',
            f'<rect x="250" y="{y-12}" width="{500*share/100:.3f}" height="9" rx="4" fill="{COLORS[i]}"/>',
            t(815, y, f"{share:.1f}%", 14, "#EEF3F6", "end"),
            t(932, y, f"{presence[lang]} / {len(data)}", 14, "#C7D3DE", "end"),
        ])
    if len(ranked) > 10:
        other = 100 * sum(volume[lang] for lang in ranked[10:]) / total
        parts.append(t(28, height-46, f"Other detected languages: {other:.1f}%", 13))
    parts.append(t(28, height-19, "Source: GitHub Linguist · selected public repositories · excludes forks and archived projects", 12, "#8E9AA7"))
    parts.append("</svg>")
    svg = "\n".join(parts) + "\n"
    ElementTree.fromstring(svg)
    return svg


def update_readme(readme):
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("Expected exactly one language analytics marker pair")
    before, rest = readme.split(START, 1)
    _, after = rest.split(END, 1)
    return before + START + '\n![Public portfolio language analytics](assets/language-stats.svg)\n' + END + after


def self_test():
    def row(name, private=False, fork=False, archived=False, owner=OWNER):
        return {"name": name, "private": private, "fork": fork,
                "archived": archived, "owner": {"login": owner}}
    assert public_portfolio([
        row("DynamisRAG"), row("DynamisSignalBench", private=True),
        row("ShoppingPal", fork=True), row("DynamisLM", archived=True),
        row("RecruiterPal", owner="someone-else"), row("unlisted")
    ]) == ["DynamisRAG"]
    data = {"a": {"Python": 80, "C#": 20}, "b": {"Python": 20, "A&B": 10}}
    volume, presence, ranked = aggregate(data)
    assert volume["Python"] == 100 and presence["Python"] == 2
    assert ranked == ["Python", "C#", "A&B"]
    assert "A&amp;B" in render(data)
    assert "76.9%" in render(data)
    sample = START + "\npending\n" + END
    assert update_readme(update_readme(sample)) == update_readme(sample)
    for invalid in ("", START + START + END):
        try:
            update_readme(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid marker pair accepted")
    print("Language analytics self-test passed")


if __name__ == "__main__":
    import sys
    self_test()
    if sys.argv[1:] != ["--self-test"]:
        root = Path(__file__).resolve().parents[1]
        data = collect()
        svg = render(data)
        readme = root / "README.md"
        updated = update_readme(readme.read_text(encoding="utf-8"))
        (root / "assets" / "language-stats.svg").write_text(svg, encoding="utf-8")
        readme.write_text(updated, encoding="utf-8")
        print(f"Generated analytics for {len(data)} public portfolio projects.")
