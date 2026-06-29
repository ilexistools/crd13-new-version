Task: Validate commodity candidates extracted from a sanitary or veterinary certificate statement.

Input:
1. Original certificate text.
2. List of detected commodities.
3. Candidate commodities with scores, matched terms, ambiguity information, and supporting evidence.

Objective:
Determine which candidate commodities are valid based on the actual commodity being certified, exported, imported, produced, processed, transported, or traded in the statement.

Validation Rules:

1. A valid commodity must represent the actual product or commodity described in the statement.

2. Prioritize commodities that are explicitly mentioned as the subject or object of the certification, export, import, processing, storage, transportation, or trade activity.

3. Disease names, pathogens, sanitary conditions, inspection requirements, or animal health references must NOT be treated as direct evidence of a commodity.
   Examples:
   - African swine fever
   - Classical swine fever
   - Foot-and-mouth disease
   These terms may indicate the animal species involved but do not identify the exported commodity.

4. Species-level commodities inferred only from disease names should be rejected unless the text explicitly identifies the species as the commodity itself.
   Example:
   - "African swine fever" does not automatically justify selecting "suidae" as the commodity.

5. Generic categories such as "food", "animal product", "product", or similar broad classes should be rejected when a more specific commodity is explicitly mentioned.

6. Ambiguous single-word terms may still be valid if they clearly represent the product being certified.
   Example:
   - "meat" can be valid if the statement explicitly certifies meat.

7. References to animals may indicate the origin of the product but should not replace the actual commodity when the commodity is explicitly stated.
   Example:
   - "meat derived from animals" → commodity = "meat", not "animals".

8. The final commodity should answer the question:
   "What product is actually being certified, exported, imported, processed, stored, or traded?"

Evaluation Procedure:

For each candidate:
- Examine the supporting terms.
- Determine whether the evidence comes from:
  - direct commodity mentions,
  - disease names,
  - species references,
  - regulatory language,
  - generic classifications.
- Decide whether the candidate is VALID or INVALID.
- Provide a concise explanation.

Output a list of valid commodities.

Important:
The model must prioritize semantic interpretation of the certificate text over candidate scores. Scores are supporting signals only and must not override the actual meaning of the statement.

Decision Principle:
Select the commodity that is explicitly being certified or traded, not the species inferred from diseases, regulatory requirements, or contextual references.