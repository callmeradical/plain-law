# Contributing a Locale

Adding your state, county, or municipality to Plain Law requires **no code** — just a YAML file.

## Quick Start

1. Find the right directory:
   - `sources/states/` — for a U.S. state
   - `sources/counties/` — for a county or parish
   - `sources/municipalities/` — for a city or town

2. Create a file named `{state}-{locality}.yaml` (e.g. `pa-philadelphia.yaml`)

3. Fill in the template below

4. Open a pull request

That's it.

---

## Template

```yaml
name: Your County, ST           # Human-readable name
type: county                    # federal | state | county | municipality
state: NJ                       # Two-letter abbreviation (if applicable)
fips: "34007"                   # FIPS code (optional but helpful)
sources:
  - type: rss                   # api | rss | scrape
    url: https://example.gov/feed.rss
    enabled: true
    notes: "Optional notes about this source."
tags: [county, nj, your-county]
maintainer: "@your-github-handle"
```

## Source Types

### `api`
For jurisdictions with a structured API (rare at county level).

```yaml
- type: api
  provider: legiscan            # legiscan | congress | custom
  url: https://api.example.com
  enabled: true
```

### `rss`
Most common. If the government body publishes an RSS or Atom feed of agendas, minutes, or legislation:

```yaml
- type: rss
  url: https://example.gov/agendas.rss
  enabled: true
```

### `scrape`
For sites with no feed. Use a CSS selector to identify the relevant elements.

```yaml
- type: scrape
  url: https://example.gov/agendas
  selector: "a[href*='agenda']"
  enabled: true
  notes: "Selector targets agenda PDF links on the page."
```

## Tips

- Set `enabled: false` if you're not sure the source works yet — it won't break anything
- You can include multiple sources for the same locale (fallback or supplemental)
- Check `sources/_schema.yaml` for the full field reference
- If your county publishes PDFs instead of HTML — open an issue, we'll add a PDF fetcher

## Finding Sources

Good places to look:
- `{county}.gov` → look for "Board of Commissioners", "County Council", "Agendas & Minutes"
- Google: `site:{county}.gov RSS feed agenda`
- [Legistar](https://legistar.com/) — many county/city councils use this platform

## Questions?

Open an issue. We'd rather help you add a locale than have you stuck.
