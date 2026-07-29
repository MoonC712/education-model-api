# Dataset decision record

## Decision

Use OECD PISA 2022 as the **primary baseline dataset** for South Korea. Do not replace it with one Korean panel or TIMSS.

## Evidence-based reasoning

A primary source must jointly support:

1. a nationally comparable Korean student sample;
2. student and school records that can be merged;
3. family-background indicators;
4. material and school resources;
5. human support;
6. digital access;
7. learning agency;
8. wellbeing;
9. public documentation and reproducible access;
10. survey weights for population estimates.

PISA meets all ten more completely than the alternatives. The alternatives are valuable as validation datasets, not substitutes.

## Important conceptual correction

The four groups must not be called “low income” and “high income.” PISA's ESCS is not household income. This package uses parental education and occupational status to construct lower/higher family-background quartiles.

## Why the resource score is separated from the grouping index

Official PISA ESCS combines PAREDINT, HISEI and HOMEPOS. Using ESCS to form groups while also using HOMEPOS in the resources vector would build part of the answer into the group definition. To reduce this circularity, this package forms groups from PAREDINT and HISEI only and reserves HOMEPOS for the resources dimension.

## Why equal weights are primary

Factor/PCA weights can make the score depend heavily on one sample and can maximise variance rather than conceptual validity. Equal weights are transparent and parallel OECD's equal-weight construction of ESCS after standardisation. PCA is retained only as a sensitivity specification.

## Why the output is a percentile

A weighted empirical percentile is interpretable and does not suggest a natural zero or a universal unit. A score of 70 means the estimated profile is above roughly 70% of Korea's weighted PISA distribution on that constructed dimension; it does not mean “70% sufficient.”

## Why factor analysis is not the primary scoring method

The five dimensions are mostly formative. Their indicators are ingredients of an opportunity state rather than interchangeable symptoms of one hidden trait. A student may have strong family support and weak teacher support; that does not invalidate the human-support dimension. Therefore, confirmatory factor analysis and Cronbach's alpha are not used as pass/fail tests. PCA, alpha and leave-one-out analyses are reported only to reveal sensitivity and redundancy.
