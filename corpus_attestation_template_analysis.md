# Corpus analysis for attestation templates

Source: `new-backend/app/assets/resources/sentences.json`

Kitconc workspace: `.kitconc_crd13`

Corpus source files: `.kitconc_crd13_sources`

## Corpus construction

The source file contains 58,019 sentence records. For template discovery, sentences were deduplicated by normalized sentence text and grouped into five analytical corpora. No source data was changed.

Composite and noisy modality labels were normalized into core regulatory modalities:

| Corpus | Unique sentences | Notes |
| --- | ---: | --- |
| `obligation` | 4,931 | Includes `Obligation`, lower-case variants, recommendations/advice, and hybrid labels containing obligation. |
| `permission` | 1,395 | Includes `Permission`, `permissive`, `option`, and hybrid labels containing permission. |
| `condition` | 1,710 | Includes `Condition`, `conditional`, and hybrid labels containing condition. |
| `limits_targets` | 710 | Includes `Limits and Targets`, `Limit`, measurement/evaluation labels, and hybrids containing limits. |
| `prohibition` | 368 | Includes `Prohibition`, negative/exclusion labels, and hybrids containing prohibition. |

## Main corpus signals

Kitconc n-grams and targeted pattern counts showed strong recurring structures:

| Regulatory modality | Frequent source structure | Corpus signal |
| --- | --- | --- |
| Obligation | `shall/must/should be + past participle` | 1,651 matched sentences |
| Obligation | `shall/must/should comply with` | 186 matched sentences; `shall comply with` and `comply with the` are high-frequency n-grams |
| Obligation | `shall/must/should be free from` | 85 matched sentences; `be free from` is frequent |
| Permission | `may + verb` | 700 matched sentences |
| Permission | `may be used/added/applied/labelled/indicated` | 203 matched sentences; `may be used` is the top 3-gram |
| Permission | `acceptable/permitted/allowed for use` | 47 matched sentences |
| Prohibition | `shall/must/should not be` | 96 matched sentences; `should not be` is the top 3-gram |
| Prohibition | `shall/must/should not contain/exceed` | 16 matched sentences |
| Limits and Targets | `not more than / not less than` | 64 matched sentences; `not more than` is the top 3-gram |
| Limits and Targets | `within the tolerances` | 49 matched sentences |
| Condition | `if/when/where/provided that/unless` | 657 matched sentences |
| Condition | `does not exceed` | 77 matched sentences; `does not exceed` and `not exceed the` are high-frequency n-grams |
| Condition | `considered as meeting` | 73 matched sentences |

## Suggested attestation template families

These templates convert regulatory source structures into certificate-style declarations of verified facts. `regulatory_modality` should preserve the normative origin; `attestation_function` should drive the drafting pattern.

| ID family | Regulatory modality | Attestation function | Suggested structural template |
| --- | --- | --- | --- |
| `ATT-OBL-COMPLIANCE` | Obligation | Compliance confirmed | `*<CertifiedSubject> comply/complies with *<StandardOrCriterion>.` |
| `ATT-OBL-STATE` | Obligation | State achieved | `*<CertifiedSubject> is/are *<CertifiedState> {[in accordance with] <ReferenceStandard>}.` |
| `ATT-OBL-ACTION` | Obligation | Action performed | `*<CertifiedSubject> has/have been *<PastParticiple> {[by] <AuthorityOrAgent>} {[in accordance with] <ReferenceStandard>}.` |
| `ATT-OBL-ABSENCE` | Obligation | Absence confirmed | `*<CertifiedSubject> is/are free from *<UndesirableCondition>.` |
| `ATT-PRO-NEG-TREATMENT` | Prohibition | Prohibited treatment absent | `*<CertifiedSubject> has/have not been *<PastParticiple> {[with/by] <ProhibitedAgentOrMethod>}.` |
| `ATT-PRO-ABSENCE` | Prohibition | Prohibited substance absent | `*<CertifiedSubject> does/do not contain *<ProhibitedSubstanceOrCondition> {[above] <Limit>}.` |
| `ATT-PRM-AUTH-USE` | Permission | Authorized use confirmed | `*<SubstanceOrAction> is/are authorized for use in *<ProductOrPurpose> {[in accordance with] <ReferenceStandard>}.` |
| `ATT-PRM-CONDITIONAL-USE` | Permission | Conditional use confirmed | `*<SubstanceOrAction> is/are used only when *<Condition>.` |
| `ATT-LIM-LIMIT-MET` | Limits and Targets | Limit met | `*<Parameter> in *<CertifiedSubject> does not exceed *<Limit>.` |
| `ATT-LIM-MINMAX` | Limits and Targets | Quantitative criterion met | `*<Parameter> in *<CertifiedSubject> is not *[more/less] than *<Limit>.` |
| `ATT-LIM-TOLERANCE` | Limits and Targets | Tolerance met | `*<CertifiedSubject> is/are within *<ToleranceReference>.` |
| `ATT-CND-CRITERIA-MET` | Condition | Acceptance criteria met | `*<CertifiedSubject> meets *<AcceptanceCriteria> when *<Condition>.` |
| `ATT-CND-CONTEXT` | Condition | Contextual condition verified | `*[When/Where/If] *<Condition>, *<CertifiedSubject> *<VerifiedStatement>.` |

## Recommended implementation approach

Add `regulatory_modality` and `attestation_function` to each new template while preserving `modality` and `communicative_function` as compatibility aliases for the current frontend.

Example:

```json
{
  "id": "ATT-OBL-COMPLIANCE-001",
  "type": "default",
  "category": "Certified compliance",
  "modality": "Obligation",
  "regulatory_modality": "Obligation",
  "attestation_function": "Compliance confirmed",
  "communicative_function": "Compliance confirmed",
  "representative_example": "Products of this consignment comply with the maximum residue limits established by the Codex Alimentarius Commission.",
  "structural_template": "*<CertifiedSubject> comply/complies with *<StandardOrCriterion>.",
  "components": {}
}
```

