# OpenRCA External Evaluation Protocol

This document defines the external-evaluation boundary for the prepared
Microsoft OpenRCA Bank and Telecom data. It is a protocol specification, not
an external accuracy result. No OpenRCA accuracy is reported until the
query-to-record mapping is independently validated.

## Input and answer separation

The model/input side may contain:

- the natural-language `instruction` with the requested incident time range;
- telemetry files selected by a documented time-window rule;
- component names and metric names derived from telemetry only;
- a documented component-name normalization map.

The model/input side must not contain:

- `scoring_points`;
- `record.csv`;
- parsed component, reason, or root-cause timestamps;
- answer-bearing text copied from any evaluator-side field;
- any query/record join artifact that exposes the answer.

`scoring_points` and `record.csv` are evaluator-only data. They may be loaded
after prediction to calculate metrics, but must not be passed to feature
generation, prompts, candidate generation, or ranking.

## Task-specific metrics

OpenRCA tasks must not be pooled into RCAEval-style service Hit@k/MRR. Report
separate denominators and metrics for:

1. **Component identification:** exact component accuracy and, when a ranked
   component list is produced, Hit@1/Hit@3/Hit@5 and MRR.
2. **Reason identification:** exact reason accuracy and a normalized-reason
   confusion matrix.
3. **Occurrence time:** absolute timestamp error in seconds/minutes, plus the
   benchmark's stated tolerance accuracy (for example, within one minute).
4. **Multi-field tasks:** report each field separately and an exact joint-match
   rate; do not replace missing fields with a success-shaped default.

Bank and Telecom must remain separate reports. Their component namespaces,
reason vocabularies, telemetry schemas, and task distributions are not
interchangeable.

## Query-to-record matching

Repeated `task_index` values are present in the prepared query files and are
not sufficient as a join key. Before scoring:

1. Parse the date, start time, end time, and requested fields from each
   instruction.
2. Normalize timestamps to a documented timezone and Unix unit.
3. Match the parsed incident window to the evaluator-side record timestamp.
4. Verify that exactly one record is matched, or document the benchmark's
   explicit disambiguation rule.
5. Verify that the matched record's component and reason are consistent with
   the query's requested output fields.
6. Write a row-level mapping audit containing the query row number, parsed
   interval, matched record row, match distance, and exclusion reason.

The current preparation report establishes file presence, row counts, and
sampled schemas, but does not establish this semantic mapping. Therefore no
external accuracy result should be claimed from the prepared files alone.

## Telemetry and candidate protocol

For each query, define before evaluation:

- the telemetry files and time interval used;
- timestamp unit conversion;
- missing-value handling;
- the candidate component universe;
- component-name normalization;
- the treatment of components with no telemetry in the requested interval.

The candidate universe must be constructed from telemetry and documented
metadata only. The evaluator-side matched record must never be used to add,
remove, reorder, or filter candidates.

## Reproducibility requirements

An external-evaluation release must preserve:

- source archive checksums and source version;
- preparation-script version;
- parsed query table with answer fields removed from model inputs;
- row-level query-to-record audit;
- excluded and ambiguous rows with reasons;
- timestamp-unit and timezone decisions;
- component/reason normalization maps;
- model configuration and random seed;
- separate Bank and Telecom result files.

Until these checks are complete, the OpenRCA work is a prepared-data
integration step, not a validated external benchmark result.
