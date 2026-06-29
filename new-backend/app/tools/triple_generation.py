from app.orchestration import gpt
from pydantic import BaseModel

class Triple(BaseModel):
    subject: str
    predicate: str
    object: str

class TripleGenerationResponse(BaseModel):
    triples: list[Triple]

class TripleGenerationTool:

    def __init__(self):
        self.__create_gpts() 

    def __create_gpts(self):
        self.__gpt_triple_generator = gpt.GPT(agent_id = 'triple_generator')
        self.__gpt_triple_generator.output_type = TripleGenerationResponse
        
    
    def run(self, text: str) -> TripleGenerationResponse:
        prompt = f"Generate triples for the following sentence: {text}"
        result = self.__gpt_triple_generator.run_sync(prompt)
        return {'input':{"text": text},'results': result.triples}

    async def run_async(self, text: str) -> dict:
        prompt = f"Generate triples for the following sentence: {text}"
        result = await self.__gpt_triple_generator.run(prompt)
        return {'input':{"text": text},'results': result.triples}
