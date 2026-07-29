# Phase 1 execution status

## Completed in this package

- Compared PISA 2022, KCYPS 2018, KELS 2013, KEEP II, the Korean youth health datasets and TIMSS 2023.
- Selected PISA 2022 as the primary unified baseline and assigned the Korean panels to later validation roles.
- Defined an auditable indicator manifest for the five dimensions.
- Implemented official-file download, resume, extraction and checksum verification.
- Implemented Korea filtering and student-school merging.
- Implemented non-circular family-background groups and rural/urban school groups.
- Implemented survey-weighted score construction, diagnostics and percentile scaling.
- Implemented Fay-BRR confidence intervals for group medians.
- Implemented four group archetypes and anonymous representative prototypes.
- Added unit tests for core weighted mathematics.

## Not executed here

The external runtime used to build this package could not transfer the multi-gigabyte OECD student file. Therefore, no real Korean vectors or group estimates are included, and no values have been invented. Running the documented fetch and pipeline commands on a machine with network access completes the numerical stage.
