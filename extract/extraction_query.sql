-- ASM Media Sentiment — Phase 2
-- Combined GKG extraction for Ghana + Brazil, 1-year pilot (2025).
-- Each row is tagged with the country/filter that matched (filter_match).
-- See asm-phase-2-plan.md for the methodology and the per-country filter rationale.
--
-- NOTE: the live gdelt-bq.gdeltv2.gkg_partitioned schema names the quote and
-- name fields `Quotations` and `AllNames` (no V2 prefix). We alias them back to
-- V2Quotations / V2AllNames so the exported dataset matches the plan's vocabulary.
--
-- ALWAYS dry-run first (bq query --dry_run) and ALWAYS pass
-- --maximum_bytes_billed=1000000000000 (1 TB) when executing for real.

SELECT
  GKGRECORDID,
  DATE,
  SourceCommonName,
  DocumentIdentifier,
  V2Themes,
  V2Tone,
  V2Locations,
  Quotations AS V2Quotations,
  AllNames AS V2AllNames,
  TranslationInfo,

  -- Tag which country filter matched (keyword takes precedence over theme).
  CASE
    WHEN (
      LOWER(DocumentIdentifier) LIKE '%galamsey%'
      OR LOWER(Quotations) LIKE '%galamsey%'
      OR LOWER(AllNames) LIKE '%galamsey%'
    ) AND (V2Locations LIKE '%GH%' OR LOWER(DocumentIdentifier) LIKE '%ghana%')
    THEN 'ghana_keyword'

    WHEN V2Themes LIKE '%WB_555%'
      AND (V2Locations LIKE '%GH%' OR LOWER(DocumentIdentifier) LIKE '%ghana%')
    THEN 'ghana_theme'

    WHEN (
      LOWER(DocumentIdentifier) LIKE '%garimpo%'
      OR LOWER(Quotations) LIKE '%garimpo%'
      OR LOWER(AllNames) LIKE '%garimpo%'
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
       OR LOWER(Quotations) LIKE '%galamsey%'
       OR LOWER(AllNames) LIKE '%galamsey%'
       OR V2Themes LIKE '%WB_555%')
      AND (V2Locations LIKE '%GH%' OR LOWER(DocumentIdentifier) LIKE '%ghana%')
    )
    OR
    -- Brazil filters
    (
      (LOWER(DocumentIdentifier) LIKE '%garimpo%'
       OR LOWER(DocumentIdentifier) LIKE '%garimpeiro%'
       OR LOWER(Quotations) LIKE '%garimpo%'
       OR LOWER(AllNames) LIKE '%garimpo%'
       OR V2Themes LIKE '%WB_555%')
      AND (TranslationInfo LIKE '%srclc:por%'
           OR V2Locations LIKE '%BR%'
           OR LOWER(DocumentIdentifier) LIKE '%brasil%'
           OR LOWER(DocumentIdentifier) LIKE '%brazil%')
    )
  )
