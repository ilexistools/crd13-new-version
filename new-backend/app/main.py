import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import Any
from pydantic import BaseModel
from PyPDF2 import PdfReader
from app.tools.commodities_identification import CommoditiesIdentifierTool
from app.tools.unitization import UnitizationTool
from app.tools.provisions_search import ProvisionsSearchTool
from app.tools.triple_generation import TripleGenerationTool
from app.tools.attestation_analyser import AttestationAnalyserTool
from app.tools.attestation_rewriter import AttestationRewriteTool
from app.tools.attestation_template_adaptation import AttestationTemplateAdapterTool
from app.tools.compliance_analysis import ComplianceAnalysisTool


unitizer = UnitizationTool()
commodities_identifier = CommoditiesIdentifierTool()
provisions_search = ProvisionsSearchTool()
triple_generator = TripleGenerationTool()
attestation_analyser = AttestationAnalyserTool()
attestation_rewriter = AttestationRewriteTool()
attestation_template_adapter = AttestationTemplateAdapterTool()
compliance_analyser = ComplianceAnalysisTool()


class InputRequest(BaseModel):
    input: dict

class OutputResponse(BaseModel):
    output: Any


app = FastAPI(title="GPT Agents + FastAPI Example")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:4200",
        "http://localhost:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "resources"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/templates")
async def templates() -> dict[str, Any]:
    templates_path = ASSETS_DIR / "attestation_templates.json"
    with templates_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

@app.post("/extract_pdf_text")
async def extract_pdf_text(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Only PDF uploads are supported.")

    try:
        reader = PdfReader(file.file)
        pages = [
            {"page": index + 1, "text": page.extract_text() or ""}
            for index, page in enumerate(reader.pages)
        ]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not extract PDF text: {exc}") from exc

    full_text = "\n".join(page["text"] for page in pages if page["text"].strip())
    return {"full_text": full_text, "pages": pages}

@app.post("/identify_commodities", response_model=OutputResponse)
async def identify_commodities(payload: InputRequest) -> OutputResponse:
    result = await commodities_identifier.run_async(payload.input.get("text", ""))
    return OutputResponse(output=result)

@app.post("/unitize", response_model=OutputResponse)
async def unitize_text(payload: InputRequest) -> OutputResponse:
    result = await unitizer.run_async(payload.input.get("text", ""))
    return OutputResponse(output=result)

@app.post("/search_provisions", response_model=OutputResponse)
async def search_provisions(payload: InputRequest) -> OutputResponse:
    result = await provisions_search.run_async(payload.input.get("commodities", []), payload.input.get("text", ""))
    return OutputResponse(output=result)    

@app.post("/generate_triples", response_model=OutputResponse)
async def generate_triples(payload: InputRequest) -> OutputResponse:
    result = await triple_generator.run_async(payload.input.get("text", ""))
    return OutputResponse(output=result)

@app.post("/analyze_attestation", response_model=OutputResponse)
async def analyze_attestation(payload: InputRequest) -> OutputResponse:
    result = await attestation_analyser.run_async(payload.input.get("attestation", ""), payload.input.get("provisions", []))
    return OutputResponse(output=result)

@app.post("/rewrite_attestation", response_model=OutputResponse)
async def rewrite_attestation_endpoint(payload: InputRequest) -> OutputResponse:
    analysis_result = payload.input.get("analysis_result")
    if analysis_result is None:
        analysis_result = payload.input.get("output")
    if analysis_result is None:
        raise HTTPException(
            status_code=422,
            detail="rewrite_attestation requires input.analysis_result",
        )
    result = await attestation_rewriter.run_async(analysis_result)
    return OutputResponse(output=result)

@app.post("/adapt_attestation_template", response_model=OutputResponse)
async def adapt_attestation_template(payload: InputRequest) -> OutputResponse:
    attestation = payload.input.get("attestation")
    if attestation is None:
        raise HTTPException(
            status_code=422,
            detail="adapt_attestation_template requires input.attestation",
        )
    result = await attestation_template_adapter.run_async(attestation)
    return OutputResponse(output=result)


    result = await compliance_analyser.run_async(attestation)
    return OutputResponse(output=result)

@app.post("/analyze_compliance", response_model=OutputResponse)
async def analyze_compliance(payload: InputRequest) -> OutputResponse:
    result = await compliance_analyser.run_async(payload.input.get("attestation", ""))
    return OutputResponse(output=result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
