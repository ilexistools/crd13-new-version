import os
from app.orchestration.gpt_agent import GPTAgent
from app.embeddings import util 
from typing import Literal, Union
from pydantic import BaseModel, Field, ConfigDict


OverallDecision = Literal[
    "keep",
    "minor_rewrite",
    "rewrite",
    "semantic_rewrite",
    "review_support",
    "human_review",
]

SupportLevel = Literal[
    "full",
    "partial",
    "weak",
    "conflicting",
    "insufficient",
]

Severity = Literal[
    "low",
    "medium",
    "high",
]


class ProvisionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provision_id: Union[str, int] = Field(
        ...,
        description="Identifier of the provision that supports, limits, contradicts, or fails to support the attestation."
    )
    evidence: str = Field(
        ...,
        description="Relevant evidence extracted or paraphrased from the provision."
    )


class IdentifiedProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion_id: int = Field(
        ...,
        description="Numeric ID of the analysis criterion that was triggered."
    )
    problem: str = Field(
        ...,
        description="Problem identified according to the selected criterion."
    )
    decision: OverallDecision = Field(
        ...,
        description="Decision associated with this specific problem."
    )
    evidence_in_attestation: str = Field(
        ...,
        description="Relevant evidence from the attestation sentence showing the problem."
    )
    evidence_in_provisions: list[ProvisionEvidence] = Field(
        default_factory=list,
        description="Relevant evidence from the supplied provisions."
    )
    explanation: str = Field(
        ...,
        description="Concise explanation of why this problem applies."
    )
    how_to_solve: str = Field(
        ...,
        description="Operational guidance for solving the identified problem."
    )
    severity: Severity = Field(
        ...,
        description="Severity of the identified problem."
    )


class AttestationAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attestation_sentence: str = Field(
        ...,
        description="The attestation sentence that was analyzed."
    )
    overall_decision: OverallDecision = Field(
        ...,
        description="Final decision based on the most serious identified problem."
    )
    support_level: SupportLevel = Field(
        ...,
        description="Degree of semantic support provided by the provisions."
    )
    identified_problems: list[IdentifiedProblem] = Field(
        default_factory=list,
        description="List of problems identified in the attestation sentence."
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Information that is missing or insufficient for a complete assessment."
    )
    final_assessment: str = Field(
        ...,
        description="Short final assessment of the attestation analysis."
    )


class AttestationAnalyserTool:

    def __init__(self):
        self.__create_gpts()
        
    def __create_gpts(self):
        criteria_path = 'app/assets/resources/rewrite_criteria.json'
        self.__rewrite_criteria = util.read_json_file(criteria_path)
        self.__gpt_agent_analyser = GPTAgent(agent_id = 'attestation_analyser')
        self.__gpt_agent_analyser.output_type = AttestationAnalysisOutput
        self.__gpt_agent_analyser.instructions += "\nRewrite criteria: " + str(self.__rewrite_criteria)
    
    async def run_async(self, attestation: str, provisions: list[dict]) -> dict:
        prompt = f"Analyze the following attestation: {attestation}\nUsing the following provisions: {provisions}"
        results = await self.__gpt_agent_analyser.run(prompt)
        return {"output":{"input": {"attestation": attestation, "provisions": provisions}, "results": results}}

    def run(self, attestation: str, provisions: list[dict]) -> dict:
        prompt = f"Analyze the following attestation: {attestation}\nUsing the following provisions: {provisions}"
        results = self.__gpt_agent_analyser.run_sync(prompt)
        return {"output":{"input": {"attestation": attestation, "provisions": provisions}, "results": results}}
