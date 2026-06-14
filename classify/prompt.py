"""Claude classification prompt for ASM news framing."""

SYSTEM_PROMPT = (
    "You are an expert analyst classifying news articles about artisanal and "
    "small-scale mining (ASM) for a media sentiment research project."
)

CLASSIFICATION_PROMPT = """\
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

8. "confidence": float 0.0-1.0

9. "rationale": string — 2-3 sentence explanation.

Return ONLY the JSON object.

--- ARTICLE ---
{article}
"""


def build_prompt(article_text: str) -> str:
    return CLASSIFICATION_PROMPT.format(article=article_text)
