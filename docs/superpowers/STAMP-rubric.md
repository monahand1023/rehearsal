# STAMP Speaking Rubric — how `engine/proficiency.py` scores

The proficiency rater scores Japanese speaking the way **Avant's STAMP** test does. This
note records the rubric and its sources so the prompt stays faithful to the real test.

## Benchmark scale (Speaking = 1–8, maps 1:1 to ACTFL)

| STAMP | ACTFL sublevel    |
|-------|-------------------|
| 1     | Novice-Low        |
| 2     | Novice-Mid        |
| 3     | Novice-High       |
| 4     | Intermediate-Low  |
| 5     | Intermediate-Mid  |
| 6     | Intermediate-High |
| 7     | Advanced-Low      |
| 8     | Advanced-Mid      |

Speaking does **not** score above 8 / Advanced-Mid (Level 9 / Advanced-High exists only on
the Reading & Listening 1–9 scale). The app reports both the STAMP number and the ACTFL name.

## Two scored axes

STAMP collapses ACTFL's FACT criteria into **two** rater decisions:

1. **Text Type** — amount and connectedness of language. The ladder:
   `words → phrases → simple/memorized sentences → detailed-but-unconnected sentences →
   loosely connected groups (some transitions) → pre-paragraph (varied connectors, time
   frames attempted, breaking down) → paragraph (time frames accurate, narration &
   description separate, handles a complication) → extended interwoven paragraph (near
   error-free, native-like)`.
2. **Accuracy = comprehensibility by audience** — can only someone *accustomed* to language
   learners understand it (and with how much effort), or could someone *unaccustomed* to
   learners understand it easily? Not an error count.

**Weighting:** Text Type dominates for levels 1–6; the two axes are balanced for 7–8 — you
cannot reach 7–8 on length alone, control and time-frame accuracy must hold.

## The biggest level discriminators

- **Amount of connected language** (single biggest lever below Advanced).
- **Connector density/variety** — none (L4) → some transitions (L5) → varied connectors (L6+).
- **Time-frame control** — present only caps ~L4–5; accurate past+present+future enables
  L6–7; interwoven near-error-free narration is L8. (Japanese: 〜た / 〜ます / 〜つもり・〜と思う.)
- **Narration vs. description interwoven** — the L7→L8 tiebreaker.
- **Self-correction & circumlocution are POSITIVES**, not penalties (ACTFL Communication
  Strategies).
- Register/politeness (です・ます vs casual) is *coaching*, not a level-determiner.

## STAMP speaking task shape

3 scored prompts, ~3-minute cap each, computer-adaptive (prompt difficulty targeted to the
test-taker). Canonical elicitation: *"A friend asks what you did over the weekend — tell
them, with who/what/when/where/why,"* engineered to draw out past-tense narration + detail.

## Sources

- STAMP Scoring Rubric (Apr 2022, verbatim rater rubric):
  https://cdnprodwpv2.avantassessment.com/wp-content/uploads/Avant-Assessment-Rubric-Breakdown-2022.pdf
- How Avant rates speaking & writing (text-type 0–8 ladder, weighting, below/avg/above):
  https://www.avantassessment.com/blog/how-does-avant-rate-speaking-and-writing-responses
- STAMP benchmarks & rubric guide (1–8 speaking / 1–9 R&L):
  https://www.avantassessment.com/guides/benchmark-rubric/stamp
- Avant STAMP and the ACTFL Proficiency Guidelines:
  https://www.avantassessment.com/blog/avant-stamp-and-the-actfl-proficiency-guidelines
- ACTFL Proficiency Guidelines 2024 — Speaking (FACT, per-sublevel descriptors):
  https://www.oregon.gov/ode/students-and-family/equity/EngLearners/Documents/ACTFL-Proficiency-Guidelines-2024.pdf
