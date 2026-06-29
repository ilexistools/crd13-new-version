import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.orchestration.gpt_agent import GPTAgent


RewriteDecision = Literal["rewritten", "unchanged", "insufficient_basis"]


class AttestationRewriteOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: RewriteDecision = Field(
        ...,
        description="Whether the attestation was rewritten, kept unchanged, or could not be safely rewritten.",
    )
    rewritten: str = Field(
        ...,
        description="Final attestation sentence. For unchanged or insufficient_basis, repeat the source exactly.",
    )
    
    rewrite_notes: list[str] = Field(
        default_factory=list,
        description="Short notes explaining preserved scope, constraints, or why no rewrite was applied.",
    )


class AttestationRewriteTool:

    def __init__(self):
        self.__create_gpts()

    def __create_gpts(self):
        self.__gpt_agent_rewriter = GPTAgent(
            agent_id="attestation_rewriter",
            output_type=AttestationRewriteOutput,
        )

   
    
    async def run_async(self, analysis_result: Any) -> dict:
        prompt = f"Rewrite the attestation based on the analysis result. If it cannot be rewritten, return it unchanged. {analysis_result}"
        results = await self.__gpt_agent_rewriter.run(prompt)
        return {"input": {"analysis_result": analysis_result}, "results": results}

    def run(self, analysis_result: Any) -> dict:
        prompt = f"Rewrite the attestation based on the analysis result. If it cannot be rewritten, return it unchanged. {analysis_result}"
        results = self.__gpt_agent_rewriter.run_sync(prompt)
        return {"input": {"analysis_result": analysis_result}, "results": results}
