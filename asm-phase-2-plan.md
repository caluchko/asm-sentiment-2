# ASM Media Sentiment — Phase 2 Implementation Plan

## Project Goal

Build a per-article analysis pipeline using GDELT's Global Knowledge Graph (GKG) via BigQuery, producing a country-level dashboard of ASM media sentiment for Ghana and Brazil. For a stratified sample of articles, classify media framing using the Claude API to go beyond dictionary-based tone scores.

## Context and Prior Findings

**Phase 1** (https://github.com/caluchko/asm-sentiment): Global ASM sentiment dashboard using GDELT DOC 2.0 API. Uses WB_555 theme filter with aggregate tone/volume timelines from 2017–present. Key limitations: aggregate-only sentiment, source country ≠ subject country, ~40% false positive rate on WB_555, non-English coverage underrepresented.

**Phase 1.5** (filter validation): Tested WB_555, keywords, and theme combinations for Ghana and Brazil. Key findings:

- **Ghana (English, control)**: `galamsey` keyword is the best filter (2,220 art/year, high precision). `"illegal mining"` adds ~600 more. WB_555 captures only 600/year (30% of galamsey). `galamsey` is 93.6% self-filtering to Ghana geographically.
- **Brazil (Portuguese)**: WB_555 captures only 24 art/year — near zero recall. `garimpo + sourcecountry:BR` returns almost nothing (3 art/year) — the sourcecountry filter is broken for translated content. `ENV_MINING + WB_2936_GOLD` returns 2,238/year but with ~7% precision due to Portuguese vocabulary collisions (Minas Gerais, ouro as gold medals, mineiro as demonym).
- **Cross-country conclusion**: A single global filter is not viable. Per-country keyword strategies are needed. WB_555 is a low-recall additive signal, not a primary filter.
- **GDELT API operational note**: The DOC API rate-limits aggressively. The `gdeltdoc` Python library has a trailing-space bug that triggers 429s. The whitelisted User-Agent from Phase 1 is required.

## Architecture

```
BigQuery GKG (single extraction query)
Search: V2Themes + DocumentIdentifier + V2Quotations
         │
         ▼
  Local parquet dataset
  (per-article: tone, locations, themes, language)
         │
         ├──► Recall validation
         │    (compare vs Phase 1.5 DOC API cached results)
         │
         ├──► Analysis pipeline
         │    (tone trends, country, minerals, language)
         │
         └──► Stratified sample (200-400 articles)
                    │
                    ▼
              Fetch article text
                    │
                    ▼
              Claude API classification
                    │
                    ▼
              Streamlit dashboard
```

## BigQuery Extraction

### Why BigQuery only (no DOC API in pipeline)

The DOC API's artlist mode only returns articles from the most recent 3 months. Since Phase 2 needs historical per-article data, BigQuery is the only viable source. The DOC API is used solely for a one-time recall validation against Phase 1.5's cached results.

### The keyword-in-metadata approach

BigQuery's GKG does not contain article full text. To find keyword-matched articles, we search the GKG fields where keywords leave traces:

- **DocumentIdentifier** (article URL): Many news URLs contain keywords. Example: `newsghana.com.gh/galamsey-fight-lethargic-act-now`
- **V2Quotations**: Extracted quoted speech from the article. Example: `"The galamsey fight is lethargic"|Speaker Name|...`
- **V2Themes**: Theme tags applied by GDELT's content analysis. WB_555, ENV_MINING, WB_2936_GOLD, etc.
- **V2AllNames**: Extracted names and significant terms. "Galamsey" as a distinctive term may be extracted here.

This will not capture every article that the DOC API's full-text search would find. The recall rate is unknown and will be measured during validation. This is a documented methodology limitation.

### Per-country filter strategy

Based on Phase 1.5 findings:

**Ghana:**
```sql
(
  -- Keyword traces in URL
  LOWER(DocumentIdentifier) LIKE '%galamsey%'
  OR LOWER(DocumentIdentifier) LIKE '%illegal%mining%'
  OR LOWER(DocumentIdentifier) LIKE '%small-scale%mining%'
  -- Keyword traces in quotes
  OR LOWER(V2Quotations) LIKE '%galamsey%'
  -- Keyword traces in extracted names/terms
  OR LOWER(V2AllNames) LIKE '%galamsey%'
  -- Theme-based (lower recall, additive)
  OR V2Themes LIKE '%WB_555%'
)
-- Galamsey is 93.6% Ghana-specific, but add location filter for precision
AND (
  V2Locations LIKE '%GH%'
  OR LOWER(DocumentIdentifier) LIKE '%ghana%'
)
```

**Brazil:**
```sql
(
  -- Keyword traces in URL
  LOWER(DocumentIdentifier) LIKE '%garimpo%'
  OR LOWER(DocumentIdentifier) LIKE '%garimpeiro%'
  -- Keyword traces in quotes
  OR LOWER(V2Quotations) LIKE '%garimpo%'
  OR LOWER(V2Quotations) LIKE '%garimpeiro%'
  -- Keyword traces in extracted names/terms
  OR LOWER(V2AllNames) LIKE '%garimpo%'
  -- Theme-based (very low recall for Brazil, but additive)
  OR V2Themes LIKE '%WB_555%'
)
-- Language filter (more reliable than sourcecountry for translated content)
AND (
  TranslationInfo LIKE '%srclc:por%'
  OR LOWER(DocumentIdentifier) LIKE '%brasil%'
  OR LOWER(DocumentIdentifier) LIKE '%brazil%'
  OR V2Locations LIKE '%BR%'
)
```

### Combined extraction query

A single query extracts both countries in one pass, tagging each article with its matched country and filter type.

```sql
SELECT
  GKGRECORDID,
  DATE,
  SourceCommonName,
  DocumentIdentifier,
  V2Themes,
  V2Tone,
  V2Locations,
  V2Quotations,
  V2AllNames,
  TranslationInfo,

  -- Tag which country filter matched
  CASE
    WHEN (
      LOWER(DocumentIdentifier) LIKE '%galamsey%'
      OR LOWER(V2Quotations) LIKE '%galamsey%'
      OR LOWER(V2AllNames) LIKE '%galamsey%'
    ) AND (V2Locations LIKE '%GH%' OR LOWER(DocumentIdentifier) LIKE '%ghana%')
    THEN 'ghana_keyword'

    WHEN V2Themes LIKE '%WB_555%'
      AND (V2Locations LIKE '%GH%' OR LOWER(DocumentIdentifier) LIKE '%ghana%')
    THEN 'ghana_theme'

    WHEN (
      LOWER(DocumentIdentifier) LIKE '%garimpo%'
      OR LOWER(V2Quotations) LIKE '%garimpo%'
      OR LOWER(V2AllNames) LIKE '%garimpo%'
    ) AND (
      TranslationInfo LIKE '%srclc:por%'
      OR V2Locations LIKE '%BR%'
      OR LOWER(DocumentIdentifier) LIKE '%brasil%'
    )
    THEN 'brazil_keyword'

    WHEN V2Themes LIKE '%WB_555%'
      AND (
        TranslationInfo LIKE '%srclc:por%'
        OR V2Locations LIKE '%BR%'
      )
    THEN 'brazil_theme'

    ELSE 'other'
  END AS filter_match

FROM `gdelt-bq.gdeltv2.gkg_partitioned`
WHERE
  _PARTITIONTIME >= TIMESTAMP("2025-01-01")
  AND _PARTITIONTIME < TIMESTAMP("2026-01-01")
  AND (
    -- Ghana filters
    (
      (LOWER(DocumentIdentifier) LIKE '%galamsey%'
       OR LOWER(DocumentIdentifier) LIKE '%illegal%mining%'
       OR LOWER(V2Quotations) LIKE '%galamsey%'
       OR LOWER(V2AllNames) LIKE '%galamsey%'
       OR V2Themes LIKE '%WB_555%')
      AND (V2Locations LIKE '%GH%' OR LOWER(DocumentIdentifier) LIKE '%ghana%')
    )
    OR
    -- Brazil filters
    (
      (LOWER(DocumentIdentifier) LIKE '%garimpo%'
       OR LOWER(DocumentIdentifier) LIKE '%garimpeiro%'
       OR LOWER(V2Quotations) LIKE '%garimpo%'
       OR LOWER(V2AllNames) LIKE '%garimpo%'
       OR V2Themes LIKE '%WB_555%')
      AND (TranslationInfo LIKE '%srclc:por%'
           OR V2Locations LIKE '%BR%'
           OR LOWER(DocumentIdentifier) LIKE '%brasil%'
           OR LOWER(DocumentIdentifier) LIKE '%brazil%')
    )
  )
```

### Cost estimate

Columns scanned for one year:

| Column | Referenced in | Estimated size (1 year) |
|---|---|---|
| V2Themes | WHERE | ~200 GB |
| DocumentIdentifier | WHERE + SELECT | ~30 GB |
| V2Quotations | WHERE + SELECT | ~100–150 GB |
| V2AllNames | WHERE | ~50–80 GB |
| V2Locations | WHERE + SELECT | ~40 GB |
| TranslationInfo | WHERE + SELECT | ~10 GB |
| V2Tone | SELECT | ~10 GB |
| DATE, SourceCommonName, GKGRECORDID | SELECT | ~15 GB |
| **Total (1 year)** | | **~450–550 GB** |

**Within the 1 TB free tier for a 1-year pilot.** For the full 2017–present range (~9 years), the total would be roughly 4–5 TB. This can be extracted at zero cost by spreading across 5 billing months (~900 GB each), or for ~$20–25 in a single month.

### Execution plan

1. **Always dry-run first**: `bq query --dry_run` to verify actual bytes before executing
2. **Set safety cap**: `--maximum_bytes_billed=1000000000000` (1 TB) on every query
3. **Start with the 1-year pilot (2025)**: validate results before committing to full historical extraction
4. **Export to local parquet**: results downloaded once, all further analysis is local

## Recall Validation

### Purpose

Measure what percentage of DOC API keyword results the BigQuery extraction captures, to quantify and document the methodology's recall limitation.

### Method

Phase 1.5 cached DOC API artlist results for the most recent 3 months. These include article URLs found by full-text keyword search for `galamsey`, `WB_555`, etc.

1. Load Phase 1.5 cached article URLs for Ghana and Brazil
2. Run the BigQuery extraction for the same 3-month window
3. Compute overlap:
   - **BigQuery recall** = URLs found by both / URLs found by DOC API
   - **BigQuery precision** = relevant articles / total BigQuery results (manual spot-check of ~50 titles)
4. Document the recall rate in the README as a known limitation

### Expected outcome

BigQuery recall will be lower than the DOC API for keyword-heavy queries (galamsey, garimpo) because not all keywords appear in URLs or quotes. The gap quantifies what we're missing. If recall is below 50%, we may need to reconsider the approach. If above 70%, the methodology is defensible.

## Data Processing

### Parse GKG fields into structured columns

```python
def parse_v2tone(tone_str: str) -> dict:
    """Parse 'tone,posScore,negScore,polarity,activityRef,selfGroupRef,wordCount'"""
    parts = str(tone_str).split(",")
    keys = ["tone", "pos_score", "neg_score", "polarity",
            "activity_ref", "self_group_ref", "word_count"]
    return {k: float(v) for k, v in zip(keys, parts) if v}

def extract_subject_countries(v2locations: str) -> list[str]:
    """Extract country codes from V2Locations field."""
    countries = set()
    for block in str(v2locations).split(";"):
        parts = block.split("#")
        if len(parts) >= 3 and parts[2].strip():
            countries.add(parts[2].strip())
    return sorted(countries)

def extract_language(translation_info: str) -> str:
    """Extract original language from TranslationInfo."""
    if not translation_info or str(translation_info).strip() == "":
        return "eng"
    for part in str(translation_info).split(";"):
        if part.strip().startswith("srclc:"):
            return part.strip().replace("srclc:", "")
    return "unknown"

def identify_minerals(v2themes: str) -> list[str]:
    """Identify minerals from co-occurring GKG themes."""
    MINERAL_THEMES = {
        "gold": ["WB_2936_GOLD", "ECON_GOLDPRICE",
                  "TAX_FNCACT_GOLD_MINERS", "TAX_FNCACT_GOLD_MINER"],
        "diamonds": ["WB_2939_DIAMONDS"],
        "cobalt": ["WB_2932_COBALT"],
        "tin": ["WB_2938_TIN"],
        "tantalum": ["WB_2941_TANTALUM"],
        "tungsten": ["WB_2940_TUNGSTEN"],
    }
    themes = str(v2themes).upper()
    found = [m for m, tags in MINERAL_THEMES.items() if any(t in themes for t in tags)]
    return found if found else ["unspecified"]
```

### Enriched dataset columns

After parsing, the local dataset has:

| Column | Source | Description |
|---|---|---|
| gkg_id | GKGRECORDID | Unique article ID |
| date | DATE | Publication datetime |
| url | DocumentIdentifier | Article URL |
| source_domain | SourceCommonName | Publisher domain |
| country | filter_match tag | Ghana or Brazil |
| filter_type | filter_match tag | keyword or theme |
| tone | V2Tone parsed | Overall tone score |
| pos_score | V2Tone parsed | Positive word score |
| neg_score | V2Tone parsed | Negative word score |
| polarity | V2Tone parsed | Polarity (pos + neg) |
| word_count | V2Tone parsed | Article length proxy |
| subject_countries | V2Locations parsed | Countries the article is about |
| original_language | TranslationInfo parsed | Source language before translation |
| minerals | V2Themes parsed | Gold, diamonds, etc. |
| themes_raw | V2Themes | Full theme list (for analysis) |

## Claude Classification

### Sampling strategy

Select 200–400 articles stratified by:
- **Country**: ~50% Ghana, ~50% Brazil
- **Year**: equal representation across the date range
- **Tone tercile**: sample negative, neutral, and positive articles equally
- **Filter type**: include both keyword-discovered and theme-discovered articles

### Article text fetching

For each sampled article:
1. Attempt to fetch full text from URL using `trafilatura`
2. If URL is dead or paywalled, construct a fallback context from:
   - Article title (from URL or extracted during BigQuery processing)
   - V2Quotations (extracted quotes give substantial content)
   - V2Themes (contextual signal)
   - V2Tone (tone breakdown)
3. Record fetch success rate — expect higher success for recent articles

### Classification prompt

```
You are an expert analyst classifying news articles about artisanal and
small-scale mining (ASM) for a media sentiment research project.

Analyse the article provided and return a JSON object with these fields:

1. "is_relevant": boolean — Is this article actually about ASM?

2. "minerals": array — Minerals referenced in ASM context.
   Options: ["gold", "diamonds", "cobalt", "tin", "tantalum",
   "tungsten", "gemstones", "sand", "coal", "other", "unspecified"]

3. "framing": string — Dominant portrayal of ASM. Choose ONE:
   - "livelihood" — economic opportunity, income, community sustenance
   - "environmental_threat" — pollution, deforestation, ecosystem damage
   - "health_hazard" — mercury poisoning, occupational injury, disease
   - "criminal_illegal" — illegal mining, smuggling, enforcement
   - "policy_progress" — formalization, regulation, international cooperation
   - "human_interest" — personal stories, community narratives
   - "gold_market" — gold price, commodity trading, supply chain
   - "child_labour" — child miners, exploitation of minors
   - "gender" — women in mining, gendered impacts

4. "secondary_framings": array — Additional framings present. May be empty.

5. "stance": string — Posture toward ASM communities/miners:
   - "sympathetic" / "critical" / "neutral" / "mixed"

6. "solution_orientation": string
   - "problem_focused" / "solution_focused" / "balanced" / "not_applicable"

7. "subject_countries": array — ISO 3166-1 alpha-2 codes.

8. "confidence": float 0.0–1.0

9. "rationale": string — 2-3 sentence explanation.

Return ONLY the JSON object.
```

### Classification pipeline

- Model: `claude-haiku-4-5-20251001` (sufficient for structured classification, ~$0.001/article)
- Rate: 0.5s delay between requests
- Truncate articles over 3,000 words
- Cache all results to disk
- Estimated cost for 300 articles: ~$0.30

## Project Structure

```
asm-sentiment-v2/
├── CLAUDE.md                     # Project context for Claude Code
├── README.md
├── requirements.txt
├── config.py                     # Filter definitions, country configs, constants
├── extract/
│   ├── bigquery_extract.py       # BigQuery query execution and export
│   └── parse_gkg.py              # Parse V2 fields into structured columns
├── validate/
│   ├── recall_validation.py      # Compare BigQuery vs Phase 1.5 DOC API results
│   └── precision_spotcheck.py    # Sample titles for manual relevance check
├── classify/
│   ├── sample.py                 # Stratified sampling logic
│   ├── fetch_text.py             # Article text fetcher with fallback
│   ├── prompt.py                 # Classification prompt template
│   └── run_classification.py     # Claude API pipeline
├── analysis/
│   ├── tone_analysis.py          # Per-article tone trends
│   ├── country_analysis.py       # Subject country extraction
│   ├── mineral_disagg.py         # Mineral identification from themes
│   └── framing_analysis.py       # Classification result analysis
├── app.py                        # Streamlit dashboard
├── data/
│   ├── raw/                      # BigQuery exports (parquet)
│   ├── processed/                # Parsed and enriched dataset
│   ├── classified/               # Claude classification results
│   └── validation/               # Recall validation outputs
└── tests/
```

## CLAUDE.md for Claude Code

```markdown
# ASM Media Sentiment — Phase 2

## Project context
Phase 2 of an ASM media sentiment analysis project.
Phase 1 repo: https://github.com/caluchko/asm-sentiment
Phase 1.5 validation data is cached in the Phase 1.5 project directory.

## Key findings from Phase 1.5
- WB_555 theme works for Ghana (600 art/year) but fails for Brazil (24 art/year)
- Keyword "galamsey" is the best Ghana filter (2,220 art/year, high precision)
- Keyword "garimpo + sourcecountry:BR" is broken (3 art/year)
- sourcecountry filter is unreliable for translated content; use sourcelang instead
- ENV_MINING + WB_2936_GOLD has ~7% precision for Brazil (vocabulary collisions)
- A single global filter is not viable; per-country strategies are needed

## Architecture
BigQuery GKG → local parquet → analysis + Claude classification → Streamlit
No DOC API in the production pipeline. DOC API only for recall validation.

## BigQuery notes
- Table: gdelt-bq.gdeltv2.gkg_partitioned
- Always include _PARTITIONTIME filter
- Always dry-run first, always set --maximum_bytes_billed
- GKG has no full article text; keywords are searched in URL, quotes, names
- 1-year pilot target: stay within 1 TB free tier
- Export results to local parquet; do not re-query for analysis

## GDELT API notes (for recall validation only)
- Rate limits aggressively; use 60s+ delays
- Whitelisted UA: "GDELT DOC Python API client 1.12.0 - https://github.com/alex9smith/gdelt-doc-api"
- gdeltdoc library has trailing-space bug; use raw requests if needed
- Phase 1.5 cached responses are in the Phase 1.5 project cache/ directory
```

## Implementation Order

1. **GCP setup** — create account, enable BigQuery API, authenticate gcloud CLI
2. **Dry-run the extraction query** — verify estimated bytes before executing
3. **Run 1-year pilot extraction (2025)** — export to local parquet
4. **Parse GKG fields** — V2Tone, V2Locations, V2Themes, TranslationInfo
5. **Recall validation** — compare BigQuery results vs Phase 1.5 cached DOC API results
6. **Precision spot-check** — manually review ~50 titles per country
7. **Build basic dashboard** — tone trends by country, source domains, language distribution
8. **Stratified sampling** — select 200–400 articles for classification
9. **Fetch article text** — attempt URL retrieval with fallback to GKG metadata
10. **Run Claude classification** — classify sample, save results
11. **Framing analysis** — add classification results to dashboard
12. **If pilot validates** — extend extraction to full 2017–present range across billing months

## Cost Summary

| Component | 1-year pilot | Full historical (2017–present) |
|---|---|---|
| BigQuery | ~500 GB (free) | ~4.5 TB ($0 if spread over 5 months, ~$22 single month) |
| Claude API (300 articles, Haiku) | ~$0.30 | ~$0.30 |
| Article text fetching | Free | Free |
| **Total** | **~$0.30** | **$0.30–$22.30** |

## Definition of Done

- [ ] BigQuery extraction complete for 1-year pilot
- [ ] GKG fields parsed into structured local dataset
- [ ] Recall validation complete with documented recall rate
- [ ] Precision spot-check complete (~50 titles per country)
- [ ] Per-article tone, subject countries, minerals, language in local dataset
- [ ] Streamlit dashboard with Ghana and Brazil views
- [ ] Stratified sample selected and classified with Claude
- [ ] Framing trends visualised in dashboard
- [ ] README with setup, methodology, and known limitations
