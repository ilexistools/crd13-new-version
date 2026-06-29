---
name: crd13-guideline-compliance-analysis
description: "Evaluates sanitary, veterinary, phytosanitary, food safety, and export certificate attestations against CRD13 guideline principles for semantic clarity, transparency, verifiability, interoperability, and preservation of meaning. Use when an agent must analyze certificate clauses, regulatory attestations, sanitary requirements, or export statements for guideline compliance issues without assessing legal validity, scientific accuracy, or policy acceptance."
---
# Guideline Compliance Analysis Skill

## Purpose

This skill evaluates sanitary, veterinary, phytosanitary, food safety, and export certificate attestations according to the **Guidelines for the Harmonized Use of Electronic Certificates**.

The skill assesses whether an attestation complies with the guideline principles related to semantic clarity, transparency, verifiability, interoperability, and preservation of meaning.

The goal is not to evaluate legal validity, scientific accuracy, regulatory acceptance, or policy compliance.

The goal is exclusively to evaluate how the attestation is expressed and whether it follows the guideline principles.

Always focus on:

- semantic clarity
- transparency
- verifiability
- interoperability
- preservation of meaning

Do not rewrite the attestation unless explicitly requested.

Your analysis must remain objective, technical, and evidence-based.

When evaluating an attestation:

1. Identify the relevant text fragment.
2. Explain your reasoning.
3. Determine compliance status:
   - Compliant
   - Partially Compliant
   - Non-Compliant
4. Identify any issue.
5. Explain why the issue affects compliance.

---

## When to Use

Use this skill whenever:

* An attestation must be evaluated against the Guidelines.
* A sanitary requirement needs compliance analysis.
* A certificate statement needs semantic assessment.
* An export certificate clause needs review.
* A regulatory statement needs decomposition into semantic units.
* A user requests identification of compliance issues related to guideline principles.

---

## Analysis Principles

The analysis is organized according to the following principles:

| Principle | Description                                          |
| --------- | ---------------------------------------------------- |
| A1        | Identification of Semantic Units                     |
| A2        | Identification of Key Attestation Elements           |
| A3        | Determination of Modality and Communicative Function |
| B1        | Break into Separate Attestations                     |
| B         | Transparency and Objectivity                         |
| C         | Verifiability and Auditability                       |
| D         | Interoperability                                     |
| E         | Preservation of Meaning                              |

---

## Required Procedure

For every attestation:

### Step 1

Read the entire attestation.

Identify:

* products
* animals
* establishments
* authorities
* countries
* zones
* diseases
* activities
* conditions
* regulatory assurances

---

### Step 2

Evaluate the attestation against each guideline principle.

For each principle:

1. Load and follow the corresponding reference file.
2. Apply only the evaluation criteria defined in that file.
3. Produce an independent assessment.

Reference files:

* A1_identification_of_semantic_units.md
* A2_identification_of_key_attestation_elements.md
* A3_determination_of_modality_and communicative_function.md
* B1_break_into_separate_attestations.md
* B_transparency_and_objectivity.md
* C_verifiability_and_auditability.md
* D_interoperability.md
* E_preservation_of_meaning.md

---

### Step 3

Do not allow conclusions from one principle to automatically determine the result of another principle.

Each principle must be evaluated independently.

---

### Step 4

After evaluating all principles, generate a consolidated report.

---

## Compliance Categories

Use only:

* Compliant
* Partially Compliant
* Non-Compliant

Do not invent additional categories.

---

## Output Format

Produce the final report using the following structure.

| Guideline Principle | Compliance | Issue Identified | Explanation |
| ------------------- | ---------- | ---------------- | ----------- |
| A1                  | ...        | ...              | ...         |
| A2                  | ...        | ...              | ...         |
| A3                  | ...        | ...              | ...         |
| B1                  | ...        | ...              | ...         |
| B                   | ...        | ...              | ...         |
| C                   | ...        | ...              | ...         |
| D                   | ...        | ...              | ...         |
| E                   | ...        | ...              | ...         |

---

## General Rules

Always remain objective.

Do not evaluate legal validity.

Do not evaluate scientific correctness.

Do not propose regulatory decisions.

Do not infer facts not explicitly stated in the attestation.

Base all conclusions exclusively on the text provided and the evaluation criteria defined in the guideline principle files.

If information is missing, state that it is not explicitly expressed in the attestation.

Always explain why a principle is compliant or non-compliant.

The analysis must be transparent, reproducible, and evidence-based.