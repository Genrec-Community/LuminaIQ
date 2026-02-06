from langchain_together import ChatTogether
from config.settings import settings
from typing import List, Dict, Any
from utils.logger import logger
import os

class LLMService:
    def __init__(self):
        os.environ['TOGETHER_API_KEY'] = settings.TOGETHER_API_KEY
        self.client = ChatTogether(
            model=settings.LLM_MODEL,
            together_api_key=settings.TOGETHER_API_KEY,
            temperature=0.7 # Default temperature, can be overridden
        )
        self.model = settings.LLM_MODEL
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Generate chat completion"""
        try:
            response = await self.client.ainvoke(
                messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            answer = response.content
            logger.info(f"Generated completion with {len(answer)} characters")
            
            return answer
            
        except Exception as e:
            logger.error(f"Error in chat completion: {str(e)}")
            raise
    
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ):
        """Generate streaming chat completion"""
        try:
            async for chunk in self.client.astream(
                messages,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                if chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            logger.error(f"Error in streaming completion: {str(e)}")
            raise

llm_service = LLMService()
