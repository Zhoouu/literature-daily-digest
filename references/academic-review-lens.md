# Academic Review Lens For Daily Digests

This reference adapts the reviewer-panel idea from Cheng-I Wu's
`academic-paper-reviewer` skill in Imbad0202/academic-research-skills
(CC BY-NC 4.0): https://github.com/Imbad0202/academic-research-skills/tree/main/academic-paper-reviewer

Use this file when turning the script's ranked paper draft into a polished
literature daily report. The goal is not to simulate a full journal decision;
it is to add a compact, evidence-grounded scholarly reading layer for each
selected paper.

## Core Rule

Separate what the source actually supports from what the analyst infers.

- Use title, abstract, metadata, DOI pages, and full text when available.
- Read local full-text artifacts linked from the generated report before writing
  full-paper analysis.
- Mark abstract-only claims explicitly.
- Do not infer results, effect sizes, datasets, limitations, or novelty that are
  not present in the retrieved evidence.
- When metadata and abstract disagree, preserve the conflict and prefer a
  cautious note over a forced conclusion.
- Do not quote long passages from retrieved full text in the final digest; use
  concise paraphrase and keep figure/text source links.

## Five Reading Lenses

### 1. Field Positioning

Identify the paper's primary field, secondary fields, research paradigm, and
target audience. Ask:

- What problem does the paper claim to address?
- Is it empirical, computational, clinical, theoretical, review, or methods work?
- Which readers would care: method developers, domain scientists, clinicians,
  policy researchers, or engineering practitioners?

### 2. Method And Evidence

Assess whether the method can answer the question at the evidence level
available in the abstract or full text.

- Empirical/clinical: design, sample, controls, endpoints, bias risk, ethics,
  statistical reporting, effect sizes, confidence intervals.
- Computational/AI: data source, train/test split, external validation,
  baselines, metrics, ablations, reproducibility, code/model availability.
- Review/meta-analysis: search strategy, inclusion criteria, bias assessment,
  heterogeneity, synthesis method.
- Theoretical/conceptual: premise clarity, inference chain, counterexamples,
  testable implications.

### 3. Domain Contribution

State the contribution as a delta: "before this paper we knew X; after it we
may know Y." Keep the claim proportional to the evidence.

- Distinguish topic novelty from intellectual contribution.
- Note whether the paper changes mechanism, method, evidence base, application
  context, dataset, benchmark, or interpretation.
- Flag missing connections to obvious adjacent literature only when you can name
  the missing area or reference family.

### 4. Devil's Advocate

Stress-test the paper with one or two strongest skeptical questions. Choose the
question most likely to matter for a reader deciding whether to read the full
paper.

Common angles:

- Does the conclusion exceed the data?
- Is there a simpler alternative explanation?
- Are the baselines, controls, or comparator methods strong enough?
- Is the sample/data distribution too narrow for the claimed scope?
- Does the abstract hide uncertainty behind broad language?

### 5. Editorial Synthesis

Conclude with a short reading recommendation, not a publication verdict.

- "必读": highly relevant and evidence-rich for the user's configured direction.
- "精读": relevant, but verify methods or full-text details.
- "略读": interesting background or adjacent signal.
- "观望": metadata-only, abstract too thin, or relevance uncertain.

Explain the recommendation in one sentence and trace it to the lenses above.

## Per-Paper Output Shape

Use this compact structure for each final digest entry:

1. Bibliographic line with DOI/source links.
2. One-sentence Chinese takeaway.
3. Four short paragraphs or bullets:
   - 研究问题与领域定位
   - 方法/数据与证据强度
   - 主要发现与学术贡献
   - 局限/反方问题/下一步阅读建议
4. Optional English note for citation-ready wording.
5. Evidence caveat, especially for abstract-only records.

## Visual Reporting

Use visuals inside each paper's interpretation, not only as dashboard-style
overviews.

- Treat ranking/source overview charts as optional diagnostics. They do not
  satisfy a figure-rich paper report by themselves.
- For individual papers, embed real figures only when a public figure image or
  full-text figure is available and citation/use terms allow it.
- If no real figure is available, use a Mermaid flow diagram only for concepts
  that can be grounded in the abstract or full text.
- Do not create decorative or speculative scientific figures.

For each paper, use this visual priority order:

1. Graphical abstract or summary figure from an accessible source.
2. Method pipeline, model architecture, experimental setup, or study design
   figure.
3. Key result figure that directly supports the paper's main claim.
4. Grounded Mermaid logic diagram based only on retrieved evidence.

When embedding a real figure, add one or two sentences explaining what the
reader should notice in the figure and how it supports or limits the paper's
claim. Preserve the figure source URL and attribution/caveat.

If the generated report links a local full-text artifact, use it to ground the
Mermaid logic diagram and figure-selection recommendation. If no full text was
retrieved, keep the diagram clearly marked as abstract/metadata-grounded.

## Daily Digest Synthesis

After per-paper notes, add a short cross-paper synthesis when there are at least
three selected papers:

- Today's strongest theme.
- Methodological pattern or gap across papers.
- One paper to read first and why.
- One caution about source coverage or evidence limitations.
