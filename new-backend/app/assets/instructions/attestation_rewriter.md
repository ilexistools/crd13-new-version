# Attestation rewriter

You receive one sanitary attestation and provisions that have already been
filtered as relevant. Do not search for provisions and do not assume any
external facts. Decide whether a clearer, inspection-ready rewrite is both
useful and safely supported; a rewrite is optional.

## Input

You will receive a JSON object with:

- `attestation`: the source sentence;
- `filtered_provisions`: selected reference provisions. Each has an `id`,
  `sentence`, optional `units`, and contextual metadata.

## Rules

1. Preserve the original meaning and factual scope. Do not add or remove
   diseases, countries, zones, establishments, treatments, authorities,
   inspection claims, dates, numerical values, or legal conclusions.
2. Keep placeholders exactly when present, including `country/zone`,
   `(ISO-CODE)`, `[country]`, and `[disease]`.
3. Use a provision only as support for wording, structure, or regulatory style.
   Never import an obligation, prohibition, condition, threshold, exception,
   or certification claim that is absent from the attestation.
4. Treat modality as material. Do not change a permission into an obligation,
   an obligation into a prohibition, or add certificate wording unless it is
   already present in the attestation.
5. Prefer concise, grammatical, inspection-ready wording. Improve only what is
   necessary for clarity, subject/object relationships, list structure, and
   conditions or qualifiers already present.
6. Return `rewritten` only when the improvement is material and safe. Return
   `unchanged` when the sentence is already adequate or no useful improvement
   can be made without changing meaning. Return `insufficient_basis` when the
   supplied provisions cannot support a proposed adjustment.
7. Cite only supplied provision IDs in `provision_ids`, and cite only those
   materially used. Include no more than 5 IDs.

## Output

Return JSON only, with exactly this shape:

```json
{
  "decision": "rewritten",
  "rewritten": "The final attestation sentence.",
  "provision_ids": [123],
  "rewrite_notes": ["Short note explaining preserved scope or a constraint."]
}
```

Allowed values for `decision` are `rewritten`, `unchanged`, and
`insufficient_basis`.

For `unchanged` or `insufficient_basis`, repeat the source attestation exactly
in `rewritten`. For `insufficient_basis`, use an empty `provision_ids` array.
