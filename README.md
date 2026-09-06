<p align="center">
  <img src="assets/CompSci_colour.png"
       alt="University of Glasgow School of Computing Science"
       width="450">
</p>
# IETF Dissertation

**MSc Computing Science Dissertation**  
**University of Glasgow**

**Student:** Haozhe Zhang  
**Supervisor:** Prof. Colin Perkins

## Project Overview

This repository contains the code, analysis scripts, outputs, and supporting
materials for my MSc Computing Science dissertation at the University of
Glasgow.

The dissertation investigates factors associated with the publication of
Internet-Drafts as RFCs within the Internet Engineering Task Force (IETF).

The analysis uses historical IETF Datatracker data and the RFC Index to
reconstruct Internet-Draft development lineages, classify publication outcomes,
and compare successful and unsuccessful development paths.

The main unit of analysis is a **development lineage**, rather than an
individual Internet-Draft revision. A lineage represents a connected sequence
of related drafts reconstructed from recorded replacement relationships.

## Research Questions

The dissertation addresses the following research questions:

1. **RQ1:** How do development and revision characteristics differ between
   successful and unsuccessful Internet-Draft lineages?

2. **RQ2:** How is recorded Working Group association related to RFC publication
   outcome?

3. **RQ3:** How are author participation and cross-organisational collaboration
   associated with RFC publication outcome?

The study is observational and focuses on association rather than causal
inference.

## Data Sources

The analysis uses the following main data sources:

- IETF Datatracker archive
- IETF Datatracker SQLite database
- RFC Index
- `ietfdata` Python library

Large local data files are not included in this repository.

Typical local data files include:

```text
data/
├── ietfdata-dt.sqlite
├── ietfdata-ma.sqlite
└── rfc-index.xml

Large database files are stored locally and are **not included in this repository**.


Methodology

The analysis pipeline consists of several stages.

1. Development Lineage Reconstruction

Internet-Drafts are grouped into development lineages using recorded
replacement relationships from the IETF Datatracker.

Connected draft relationships are reconstructed using a Union-Find based
approach.

2. Publication Outcome Classification

Each lineage is classified according to its development outcome.

The main outcome categories are:

Successful
Unsuccessful
Ongoing
Recently Expired
Unknown / Other

RFC publication evidence takes priority when classifying successful lineages.

For lineages without an RFC, inactivity after draft expiry is used to
distinguish unsuccessful development from recently expired work.

An 18-month post-expiry inactivity threshold is used in the primary analysis.

3. Working Group Association

Recorded Working Group information from the Datatracker is used to examine the
relationship between Working Group association and publication outcome.

The analysis distinguishes between:

lineages with recorded Working Group association;
lineages without recorded Working Group association;
Individual-to-Working-Group development transitions.

The term "recorded Working Group association" is used because Datatracker
metadata may not capture every form of actual Working Group involvement.

4. Author and Organisation Analysis

Datatracker author records are used to reconstruct participation at the lineage
level.

Organisation aliases and temporal affiliation information are used to estimate
author affiliations.

Cross-organisational collaboration is identified when authors associated with
two or more organisations appear on the same draft.

5. Statistical Analysis

The primary comparison is between successful and unsuccessful lineages.

Numerical variables are analysed using:

median;
interquartile range;
Mann-Whitney U test;
rank-biserial correlation.

Categorical variables are analysed using:

contingency tables;
chi-square tests;
Cramer's V;
odds ratios.

The analysis is intended to identify associations rather than establish
causality.

Lineage Reconstruction Cross-check

An additional consistency check is used to investigate whether missing
Datatracker relationships could split an Individual draft and a later Working
Group draft into separate reconstructed lineages.

The cross-check uses three stages:

specific topic-name matching;
chronological consistency;
shared Datatracker author identities.

Generic topic components with low discriminative value are excluded from the
name-based stage.

Candidate pairs identified by this process are treated as possible missing
relationships and are not automatically merged into the primary dataset.

ietf-dissertation/
│
├── data/
│   └── Local Datatracker and RFC data
│
├── scripts/
│   ├── pipeline/
│   │   ├── 00_build_history.py
│   │   ├── 01_classify_success.py
│   │   ├── 02_classify_wg_v2.py
│   │   ├── 03_inspect_terminal_states.py
│   │   └── 04_classify_outcomes.py
│   │
│   ├── rq1/
│   │   ├── 09_analyse_rq1.py
│   │   └── 09b_rq1_ecdf.py
│   │
│   ├── rq2/
│   │   └── 10_analyse_rq2.py
│   │
│   ├── rq3/
│   │   ├── 05_prepare_organisations.py
│   │   ├── 06_prepare_participants.py
│   │   ├── 07_prepare_affiliations.py
│   │   ├── 08_build_rq3_collaboration.py
│   │   └── 11_analyse_rq3.py
│   │
│   └── validation/
│       ├── crosscheck_lineages.py
│       ├── expired_date_threshold.py
│       └── inspect_generic_topics.py
│
├── outputs/
│   ├── common/
│   ├── intermediate/
│   ├── rq1/
│   ├── rq2/
│   ├── rq3/
│   └── validation/
│       ├── expiry/
│       └── lineage_crosscheck/
│
├── references/
│   └── Supporting research papers
│
├── report/
│   └── Dissertation source files
│
└── README.md

Main Analysis Workflow

The main dataset construction pipeline is:

00_build_history.py
        ↓
01_classify_success.py
        ↓
02_classify_wg_v2.py
        ↓
03_inspect_terminal_states.py
        ↓
04_classify_outcomes.py

Research question analyses are then performed using:

RQ1
09_analyse_rq1.py
09b_rq1_ecdf.py

RQ2
10_analyse_rq2.py

RQ3
05_prepare_organisations.py
06_prepare_participants.py
07_prepare_affiliations.py
08_build_rq3_collaboration.py
11_analyse_rq3.py

Supporting methodological checks are implemented separately:

expired_date_threshold.py
crosscheck_lineages.py
inspect_generic_topics.py
Main Outputs

Common lineage-level outputs are stored under:

outputs/common/

Research-question-specific results are stored under:

outputs/rq1/
outputs/rq2/
outputs/rq3/

Methodological checks are stored under:

outputs/validation/expiry/
outputs/validation/lineage_crosscheck/

These directories contain summary tables, statistical results, and figures used
in the dissertation.

Notes

Large Datatracker database files are intentionally excluded from the repository.

Some historical Datatracker metadata may be incomplete, particularly for
replacement relationships and Working Group transitions. These limitations are
considered explicitly in the dissertation methodology and discussion.
