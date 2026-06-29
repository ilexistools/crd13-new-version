import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.orchestration.gpt_agent import GPTAgent


CorrectionDecision = Literal["corrected", "unchanged", "insufficient_basis"]


class ComplianceCorrectionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: CorrectionDecision = Field(
        ...,
        description="Whether the attestation was corrected, kept unchanged, or could not be safely corrected.",
    )
    corrected_attestation: str = Field(
        ...,
        description="Final attestation text. For unchanged or insufficient_basis, repeat the source exactly.",
    )
    applied_principles: list[str] = Field(
        default_factory=list,
        description="Guideline principle codes whose authorized issues were addressed.",
    )
    correction_notes: list[str] = Field(
        default_factory=list,
        description="Short notes explaining the changes made or why no correction was applied.",
    )


class ComplianceCorrectionTool:

    def __init__(self):
        self.__create_gpts()

    def __create_gpts(self):
        self.__gpt_agent_corrector = GPTAgent(
            agent_id="compliance_corrector",
            output_type=ComplianceCorrectionOutput,
        )

    async def run_async(
        self,
        attestation: str,
        compliance_analysis: dict[str, Any],
        allowed_principles: list[str],
    ) -> dict:
        cleaned_attestation = str(attestation or "").strip()
        cleaned_principles = [str(item).strip() for item in allowed_principles if str(item).strip()]

        if not cleaned_attestation or not cleaned_principles:
            return {
                "input": {
                    "attestation": cleaned_attestation,
                    "compliance_analysis": compliance_analysis,
                    "allowed_principles": cleaned_principles,
                },
                "results": {
                    "decision": "unchanged",
                    "corrected_attestation": cleaned_attestation,
                    "applied_principles": [],
                    "correction_notes": ["No principle was authorized for correction."],
                },
            }

        prompt = (
            "Correct the attestation only for the authorized compliance principles.\n"
            f"Attestation: {cleaned_attestation}\n"
            f"Authorized principles: {cleaned_principles}\n"
            "Compliance analysis JSON:\n"
            f"{json.dumps(compliance_analysis or {}, ensure_ascii=False)}"
        )
        results = await self.__gpt_agent_corrector.run(prompt)
        return {
            "input": {
                "attestation": cleaned_attestation,
                "compliance_analysis": compliance_analysis,
                "allowed_principles": cleaned_principles,
            },
            "results": results,
        }

    def run(
        self,
        attestation: str,
        compliance_analysis: dict[str, Any],
        allowed_principles: list[str],
    ) -> dict:
        cleaned_attestation = str(attestation or "").strip()
        cleaned_principles = [str(item).strip() for item in allowed_principles if str(item).strip()]

        if not cleaned_attestation or not cleaned_principles:
            return {
                "input": {
                    "attestation": cleaned_attestation,
                    "compliance_analysis": compliance_analysis,
                    "allowed_principles": cleaned_principles,
                },
                "results": {
                    "decision": "unchanged",
                    "corrected_attestation": cleaned_attestation,
                    "applied_principles": [],
                    "correction_notes": ["No principle was authorized for correction."],
                },
            }

        prompt = (
            "Correct the attestation only for the authorized compliance principles.\n"
            f"Attestation: {cleaned_attestation}\n"
            f"Authorized principles: {cleaned_principles}\n"
            "Compliance analysis JSON:\n"
            f"{json.dumps(compliance_analysis or {}, ensure_ascii=False)}"
        )
        results = self.__gpt_agent_corrector.run_sync(prompt)
        return {
            "input": {
                "attestation": cleaned_attestation,
                "compliance_analysis": compliance_analysis,
                "allowed_principles": cleaned_principles,
            },
            "results": results,
        }
