
This dashboard analyses one year (2025) of online news coverage of artisanal and
small-scale mining (ASM) in **Ghana** and **Brazil** — how much coverage there
is, how its tone moves over time, which minerals and places it concerns, and how
it frames the people and the activity. Articles are analysed by sentiment, and a subset are further classified with an LLM to obtain more detailed information than sentiment alone.

#### Data Source
Data come from GDELT's Global Knowledge Graph (GKG), a
continuously updated, machine-generated index of worldwide online news, queried
here through BigQuery over the full 2025 calendar year.
GKG stores no article body text — only metadata: the web address,
the topics GDELT detects, a tone score, the people and organisations named, the
geographic locations referenced, extracted quotations, and translation
information.

#### Identifying ASM coverage, country by country
A single global search for ASM presents a limitation: the activity is named differently in each country, the vocabulary collides with unrelated uses, and GDELT's own country labels are unreliable for translated articles. Earlier validation work confirmed that the filter based on the World Bank Theme Taxonomy's ASM theme either misses Brazil almost entirely or admits large numbers of false positives. This dashboard therefore applies a **separate, tailored search for each country**, and records which clause caught each article:

- **Ghana** — the local term *galamsey* (or the broader *illegal mining*),
  detected in the address, quotations, or named entities, together with the World Bank's
  small-scale-mining topic tag, gated to articles carrying a Ghana location
  signal. *Galamsey* is almost exclusively Ghanaian, which makes it the
  highest-precision filter in the study.
- **Brazil** — the Portuguese terms *garimpo* / *garimpeiro* (informal mining /
  informal miner) and the same topic tag, gated to a Portuguese-language or
  Brazil signal. Language is used as the primary gate because GDELT's
  source-country field proved unreliable for translated coverage.

These are parallel searches, not a sequence of filters: an article is kept if it
matches the Ghana clause **or** the Brazil clause, and is then labelled by
whichever clause matched (a country keyword taking precedence over the topic
tag). The first diagram below shows how the year's articles divide between the
two countries and between keyword and topic matches. A residual group of
articles is caught by the broad terms but cannot be confidently tied to either
country; these are reported as *unattributed* and excluded from the country and
framing results.

#### What is measured for each article
From each record's metadata the pipeline
derives the quantities shown across the dashboard's tabs: a **tone** score
(GDELT's lexical sentiment measure, charted over time and by distribution); the **original language** of the article before any
translation; and the **subject countries** the article refers to, taken from its
geographic references. Together these describe the shape and reach of the
coverage before any judgement is made about how it is framed.

#### Classifying the article framing for more insights
Counts and tone show *how much* coverage exists and
its broad sentiment, but not *how* mining and miners are portrayed. To capture
that, a **stratified sample** is drawn across the four country-and-filter groups
so each is adequately represented, and each sampled article is read by an AI
model (Claude) and assigned a structured set of labels: its **primary framing**
(for example environmental threat, criminality, livelihood, health, or policy
progress), any **secondary framings**, its **stance** toward miners (critical,
mixed, neutral, or sympathetic), and its **solution orientation** (whether it
dwells on problems or points toward solutions).

Because GKG holds no body text, each sampled article is classified on the best
text available, in tiers: the full article is fetched and read where possible;
where the link is dead or paywalled but GKG preserved genuine quotations, those
quotations plus the article's topics and tone form a substantive basis for
classification. Articles with **neither** recoverable text **nor** quotations
are set aside rather than classified, because the only remaining signal — topics
and tone — is circular with the filter that surfaced the article. Of the
articles that are classified, those the model judges not actually to concern ASM
are also removed. The second diagram below traces this funnel from the initial
sample to the final framing analysis set, on which all framing, stance, and
solution-orientation results are computed.

