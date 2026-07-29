# Narrative Validation Method

## Purpose

The narrative module is not treated as valid simply because it produces plausible-looking vectors. It must be tested against independent human coding.

## Coding unit

Each decision is one:

```text
narrative × indicator
```

The nominal levels are:

```text
unknown, very_low, low, typical, high, very_high
```

## Human coding design

1. Use at least two independent coders.
2. Coders receive the schema and narratives but not the algorithm proposals.
3. Each coder selects one level and cites the exact evidence phrase.
4. Exact agreement forms a conservative two-coder consensus.
5. Disagreement remains unresolved and is excluded from algorithm-versus-consensus analysis.

## Metrics

### Exact agreement

The proportion of identical decisions.

### Cohen’s kappa

Chance-corrected agreement for two coders on nominal categories:

```text
kappa = (observed agreement - expected agreement) / (1 - expected agreement)
```

The implementation follows the standard definition introduced by Jacob Cohen (1960). Kappa is reported with sample sizes and exact agreement because prevalence can affect interpretation.

### Unknown-detection accuracy

The proportion of cases where the algorithm correctly identifies whether evidence is unknown. This is especially important because the model must not convert silence into disadvantage.

### Optional vector accuracy

When a separately constructed human-reference vector is available:

- Mean absolute error.
- Spearman rank correlation.
- Results per vector dimension.

## Revision rule

A weak result does not justify changing the final numbers until they look better. Review:

- Indicator definition.
- Phrase rules.
- Ambiguous wording.
- Conflicting cues.
- Human disagreement.
- Narrative coverage.

Document every schema change and rerun the validation on a held-out set where possible.
