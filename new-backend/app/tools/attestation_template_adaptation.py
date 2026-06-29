import json
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.orchestration.gpt_agent import GPTAgent


TemplateAdaptationDecision = Literal[
    "adapted",
    "not_adapted_review_required",
]

ComponentStatus = Literal[
    "filled",
    "omitted_optional",
    "missing_required",
    "not_applicable",
]


class SelectedTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Optional[str] = None
    category: Optional[str] = None
    modality: Optional[str] = None
    communicative_function: Optional[str] = None
    structural_template: Optional[str] = None


class ComponentMappingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_name: str
    value: str = ""
    source_text: str = ""
    status: ComponentStatus
    preservation_note: str


class InformationPreservationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preserves_subject_or_commodity: bool
    preserves_assurance: bool
    preserves_process_or_activity: bool
    preserves_conditions_or_qualifiers: bool
    preserves_limits_or_parameters: bool
    preserves_agent_or_authority: bool
    preserves_reference_standard: bool
    preserves_modality: bool
    preserves_communicative_function: bool
    does_not_add_unsupported_information: bool
    does_not_remove_essential_information: bool
    does_not_strengthen_claim: bool
    does_not_weaken_claim: bool


class UnmappedInformation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    reason: str
    essential: bool


class AlternativeTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    fit_score: float = Field(ge=0.0, le=1.0)
    reason: str


class AttestationTemplateAdapterOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_attestation: str

    template_adaptation_decision: TemplateAdaptationDecision

    selected_template: SelectedTemplate

    adapted_attestation: Optional[str] = None

    component_mapping: List[ComponentMappingItem] = Field(default_factory=list)

    template_selection_rationale: str

    information_preservation_check: InformationPreservationCheck

    unmapped_information: List[UnmappedInformation] = Field(
        default_factory=list
    )

    alternative_templates: List[AlternativeTemplate] = Field(
        default_factory=list
    )

    confidence: float = Field(ge=0.0, le=1.0)

    unresolved_risks: List[str] = Field(default_factory=list)

    final_assessment: str


class AttestationTemplateAdapterTool:
     
    def __init__(self):
        self.__create_gpts()

    def __create_gpts(self):
        self.__gpt_agent_adapter = GPTAgent(
            agent_id="attestation_template_adapter",
            output_type=AttestationTemplateAdapterOutput,
        )

    
    async def run_async(self, attestation: str) -> dict:
        prompt = json.dumps({"attestation_sentence": attestation}, ensure_ascii=False)
        results = await self.__gpt_agent_adapter.run(prompt)
        return {"input": {"attestation": attestation}, "results": results}

    def run(self, attestation: str) -> dict:
        prompt = json.dumps({"attestation_sentence": attestation}, ensure_ascii=False)
        results = self.__gpt_agent_adapter.run_sync(prompt)
        return {"input": {"attestation": attestation}, "results": results}
