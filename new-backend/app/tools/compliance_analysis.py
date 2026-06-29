import os
from app.orchestration.gpt_agent import GPTAgent
from app.embeddings import util 
from typing import Literal, Union
from pydantic import BaseModel, Field

class OverallAssessment(BaseModel):
    compliance: str = Field(
        description="Use only: Compliant, Partially Compliant, or Non-Compliant."
    )
    summary: str


class PrincipleAssessment(BaseModel):
    principle: str = Field(
        description="Guideline principle code: A1, A2, A3, B1, B, C, D, or E."
    )
    principle_name: str
    compliance: str = Field(
        description="Use only: Compliant, Partially Compliant, or Non-Compliant."
    )
    relevant_text_fragment: str
    issue_identified: str
    explanation: str


class IdentifiedElements(BaseModel):
    products: list[str] = Field(default_factory=list)
    animals: list[str] = Field(default_factory=list)
    establishments: list[str] = Field(default_factory=list)
    authorities: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    zones: list[str] = Field(default_factory=list)
    diseases: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    regulatory_assurances: list[str] = Field(default_factory=list)


class GuidelineComplianceAnalysisOutput(BaseModel):
    attestation: str
    overall_assessment: OverallAssessment
    principle_assessments: list[PrincipleAssessment]
    identified_elements: IdentifiedElements
    missing_information: list[str] = Field(default_factory=list)
    final_assessment: str


class ComplianceAnalysisTool(BaseModel):

    def __init__(self):
        self.__create_gpts()
        
    def __create_gpts(self):
        self.__gpt_agent_analyser = GPTAgent(agent_id = 'compliance_analyser')
        self.__gpt_agent_analyser.output_type = GuidelineComplianceAnalysisOutput
        
    async def run_async(self, attestation: str) -> dict:
        prompt = f"Analyze the following attestation: {attestation}"
        results = await self.__gpt_agent_analyser.run(prompt)
        return {"output":{"input": {"attestation": attestation}, "results": results}}

    def run(self, attestation: str) -> dict:
        prompt = f"Analyze the following attestation: {attestation}"
        results = self.__gpt_agent_analyser.run_sync(prompt)
        return {"output":{"input": {"attestation": attestation}, "results": results}}
