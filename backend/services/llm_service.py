from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from config.settings import settings
from typing import List, Dict, Any
from utils.logger import logger


class LLMService:
    def __init__(self):
        self.azure_endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.azure_api_key = settings.AZURE_OPENAI_API_KEY
        self.azure_deployment = settings.AZURE_OPENAI_DEPLOYMENT
        self.azure_api_version = settings.AZURE_OPENAI_API_VERSION
    
    def _get_client(self, temperature: float = 0.7, max_tokens: int = 1000):
        """Create an Azure OpenAI client with specific settings"""
        return AzureChatOpenAI(
            azure_endpoint=self.azure_endpoint,
            azure_deployment=self.azure_deployment,
            api_key=self.azure_api_key,
            api_version=self.azure_api_version,
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
            
            logger.info(f"Sending {len(lc_messages)} messages to Azure OpenAI (temp={temperature}, max_tokens={max_tokens})")
            
            response = await client.ainvoke(lc_messages)
            
            answer = response.content if getattr(response, 'content', None) else ""
            if not answer:
                logger.warning(f"[LLMService] Empty response detected. Metadata: {getattr(response, 'response_metadata', 'No metadata')}")

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
