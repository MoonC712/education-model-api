# Intervention time method

## Endpoint logic

Each intervention first defines an evidence- or programme-based endpoint on one underlying PISA-aligned indicator. Quality and dosage determine how much of that endpoint is available:

\[
E_a = qd
\]

where \(q,d\in[0,1]\).

## Time response

The realised fraction after \(t\) months is:

\[
G_a(t)=1-2^{-t/h_a}
\]

where \(h_a>0\) is the intervention-specific implementation/adoption half-time.

At \(t=h_a\):

\[
G_a(h_a)=\frac12
\]

The implemented strength is:

\[
I_a(t)=qdG_a(t)
\]

For a direct gap-closing intervention:

\[
x_i(t)=x_i(0)+I_a(t)\max\{0,x_a^*-x_i(0)\}
\]

For an evidence-based standardised shift:

\[
x_i(t)=\min\{x_i(0)+I_a(t)\tau_a,\;c_a\}
\]

where \(\tau_a\) is the selected scenario effect and \(c_a\) is the reference cap.

## Why this fixes the horizon problem

The previous rule was linear and clipped at 1. Once a programme reached its implementation month, later horizons were identical. The new curve is strictly increasing for every finite positive \(t\) and approaches 1 asymptotically, so 1, 6, 12, and 24 months remain distinct for a responsive profile.

The model does **not** force movement when:

- the target baseline indicator is missing;
- the student already meets the target or cap;
- quality or dosage is zero.

Those zero-change cases are substantive results, not time-model errors.

## Interpretation boundary

The time curve is a transparent implementation/adoption scenario. It is not evidence that a child's development follows an exponential law. Intervention-specific half-times are visible in `config/intervention_manifest.json` and can be revised when stronger longitudinal evidence is available.
