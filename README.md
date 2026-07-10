# IETF Dissertation

**MSc Computing Science Dissertation**

**University of Glasgow**

Student: Haozhe Zhang

Supervisor: Prof. Colin Perkins


## Project Overview

This repository contains the code, analysis scripts, and research reports for my MSc dissertation at the University of Glasgow.

The project investigates factors that influence the successful development of Internet standards within the Internet Engineering Task Force (IETF). The research uses the official IETF Datatracker archive together with metadata extracted from the Datatracker SQLite database.

The objective is to identify characteristics associated with successful Internet-Drafts and understand how different aspects of the standardisation process relate to document outcomes.


## Research Questions

Current research questions include:

- What factors influence whether an Internet-Draft becomes an RFC?
- Does participation within working groups affect document success?
- Does document revision history influence the probability of publication?
- How does the duration of the standardisation process relate to success?
- Can characteristics of the development process be used to predict document outcomes?

These questions may be refined as the project develops.


## Data Source

The analysis is based on the official IETF Datatracker archive.

Main dataset:

- ietfdata-dt.sqlite

The SQLite database contains metadata describing

- Internet-Drafts
- RFCs
- Working Groups
- States
- Document history
- Authors
- Events

Large database files are stored locally and are **not included in this repository**.


## Methodology

The planned workflow is:

1. Explore the Datatracker schema
2. Extract relevant metadata
3. Clean and preprocess the data
4. Engineer useful analysis features
5. Perform statistical analysis
6. Build predictive models
7. Visualise and interpret results

The repository is organised according to this workflow.
Raw SQLite Database
        │
SQL Extraction
        │
CSV Dataset
        │
Data Cleaning
        │
Feature Engineering
        │
Exploratory Analysis
        │
Statistical Analysis
        │
Machine Learning
        │
        ▼
     Results

