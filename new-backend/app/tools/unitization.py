from app.orchestration import gpt
from app.orchestration.config import default_model
from app.orchestration.util import instruction_loader
import spacy
from pydantic import BaseModel

class UnitizationResponse(BaseModel):
    units: list[str]

class UnitizationTool:

    def __init__(self):
        self.__create_gpts() 

    def __create_gpts(self):
        self.__gpt_unitizer = gpt.GPT(agent_id = 'unitizer')
        self.__gpt_unitizer.output_type = UnitizationResponse
        
    
    def run(self, text: str) -> UnitizationResponse:
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text)
        sentences = [sent.text for sent in doc.sents]
        prompt = f"Break down the following text into smaller, manageable units: {'\n'.join(sentences)}"
        result = self.__gpt_unitizer.run_sync(prompt)
        return {'input':{"text": text},'results': result.units}

    async def run_async(self, text: str) -> dict:
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text)
        sentences = [sent.text for sent in doc.sents]
        prompt = f"Break down the following text into smaller, manageable units: {'\n'.join(sentences)}"
        result = await self.__gpt_unitizer.run(prompt)
        return {'input':{"text": text},'results': result.units}
