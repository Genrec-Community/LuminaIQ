from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from config.settings import settings
from typing import List, Dict, Any
from utils.logger import logger
import os

class LLMService:
    def __init__(self):
        os.environ['OPENAI_API_KEY'] = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL
    
    def _get_client(self, temperature: float = 0.7, max_tokens: int = 1000):
        """Create a client with specific settings"""
        return ChatOpenAI(
            model=self.model,
            openai_api_key=self.api_key,
            openai_api_base=self.base_url,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    def _convert_messages(self, messages: List[Dict[str, str]]):
        """Convert dict messages to LangChain message objects"""
        converted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "user":
                converted.append(HumanMessage(content=content))
            elif role == "assistant":
                converted.append(AIMessage(content=content))
            elif role == "system":
                converted.append(SystemMessage(content=content))
            else:
                converted.append(HumanMessage(content=content))
        
        return converted
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Generate chat completion"""
        try:
            # Create client with specific settings
            client = self._get_client(temperature=temperature, max_tokens=max_tokens)
            
            # Convert messages to LangChain format
            lc_messages = self._convert_messages(messages)
            
            logger.info(f"Sending {len(lc_messages)} messages to LLM (temp={temperature}, max_tokens={max_tokens})")
            
            response = await client.ainvoke(lc_messages)
            
            answer = response.content if response.content else ""
            logger.info(f"Generated completion with {len(answer)} characters")
            
            return answer
            
        except Exception as e:
            logger.error(f"Error in chat completion: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ):
        """Generate streaming chat completion"""
        try:
            # Create client with specific settings
            client = self._get_client(temperature=temperature, max_tokens=max_tokens)
            
            # Convert messages to LangChain format
            lc_messages = self._convert_messages(messages)
            
            async for chunk in client.astream(lc_messages):
                if chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            logger.error(f"Error in streaming completion: {str(e)}")
            raise

llm_service = LLMService()
