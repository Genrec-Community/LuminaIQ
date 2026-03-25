from typing import List, Optional, Dict, Any
from db.client import get_supabase_client
from utils.logger import logger
from services.rag_service import rag_service
from services.llm_service import llm_service
from utils.performance import PerformanceTracker
import json
import re

class FlashcardService:
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def get_flashcard_sets(self, user_id: str, project_id: str) -> List[Dict[str, Any]]:
        """Get all flashcard sets for a project with card counts"""
        try:
            # Get flashcard sets
            response = self.supabase.table('flashcard_sets') \
                .select('*') \
                .eq('user_id', user_id) \
                .eq('project_id', project_id) \
                .order('created_at', desc=True) \
                .execute()
            
            sets = response.data or []
            
            # Get card counts and cards for each set
            for flashcard_set in sets:
                cards_response = self.supabase.table('flashcards') \
                    .select('id', count='exact') \
                    .eq('set_id', flashcard_set['id']) \
                    .execute()
                
                flashcard_set['card_count'] = cards_response.count or 0
                
                # Get cards for the set
                cards_data = self.supabase.table('flashcards') \
                    .select('*') \
                    .eq('set_id', flashcard_set['id']) \
                    .order('position') \
                    .execute()
                
                flashcard_set['cards'] = cards_data.data or []
            
            return sets
        
        except Exception as e:
            logger.error(f"Error fetching flashcard sets: {e}")
            raise Exception(f"Failed to fetch flashcard sets: {str(e)}")
    
    async def create_flashcard_set(
        self,
        user_id: str,
        project_id: str,
        title: str,
        topic: Optional[str],
        description: Optional[str],
        cards: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Create a new flashcard set with cards"""
        try:
            # Create the set
            set_data = {
                'user_id': user_id,
                'project_id': project_id,
                'title': title,
                'topic': topic,
                'description': description
            }
            
            set_response = self.supabase.table('flashcard_sets') \
                .insert(set_data) \
                .execute()
            
            if not set_response.data:
                raise Exception("Failed to create flashcard set")
            
            flashcard_set = set_response.data[0]
            set_id = flashcard_set['id']
            
            # Create the cards
            if cards:
                cards_data = [
                    {
                        'set_id': set_id,
                        'front': card['front'],
                        'back': card['back'],
                        'position': idx
                    }
                    for idx, card in enumerate(cards)
                ]
                
                cards_response = self.supabase.table('flashcards') \
                    .insert(cards_data) \
                    .execute()
                
                flashcard_set['cards'] = cards_response.data or []
                flashcard_set['card_count'] = len(flashcard_set['cards'])
            else:
                flashcard_set['cards'] = []
                flashcard_set['card_count'] = 0
            
            logger.info(f"Created flashcard set {set_id} with {len(cards)} cards")
            return flashcard_set
        
        except Exception as e:
            logger.error(f"Error creating flashcard set: {e}")
            raise Exception(f"Failed to create flashcard set: {str(e)}")
    
    async def update_flashcard_set(
        self,
        user_id: str,
        set_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a flashcard set"""
        try:
            response = self.supabase.table('flashcard_sets') \
                .update(updates) \
                .eq('id', set_id) \
                .eq('user_id', user_id) \
                .execute()
            
            if not response.data:
                raise Exception("Flashcard set not found or unauthorized")
            
            return response.data[0]
        
        except Exception as e:
            logger.error(f"Error updating flashcard set: {e}")
            raise Exception(f"Failed to update flashcard set: {str(e)}")
    
    async def delete_flashcard_set(self, user_id: str, set_id: str):
        """Delete a flashcard set (cards will be deleted via CASCADE)"""
        try:
            response = self.supabase.table('flashcard_sets') \
                .delete() \
                .eq('id', set_id) \
                .eq('user_id', user_id) \
                .execute()
            
            if not response.data:
                raise Exception("Flashcard set not found or unauthorized")
            
            logger.info(f"Deleted flashcard set {set_id}")
        
        except Exception as e:
            logger.error(f"Error deleting flashcard set: {e}")
            raise Exception(f"Failed to delete flashcard set: {str(e)}")
    
    async def get_flashcards(self, user_id: str, set_id: str) -> List[Dict[str, Any]]:
        """Get all flashcards in a set"""
        try:
            # Verify ownership
            set_response = self.supabase.table('flashcard_sets') \
                .select('id') \
                .eq('id', set_id) \
                .eq('user_id', user_id) \
                .execute()
            
            if not set_response.data:
                raise Exception("Flashcard set not found or unauthorized")
            
            # Get cards
            response = self.supabase.table('flashcards') \
                .select('*') \
                .eq('set_id', set_id) \
                .order('position') \
                .execute()
            
            return response.data or []
        
        except Exception as e:
            logger.error(f"Error fetching flashcards: {e}")
            raise Exception(f"Failed to fetch flashcards: {str(e)}")

    async def generate_flashcards_with_ai(
        self,
        user_id: str,
        project_id: str,
        topic: str,
        num_cards: int,
        selected_documents: List[str]
    ) -> Dict[str, Any]:
        """Generate flashcards using AI based on document content"""
        perf = PerformanceTracker()
        perf.start("flashcard_generation_total")
        try:
            # Get relevant context from documents
            context = ""
            perf.start("rag_context_fetch")
            if selected_documents:
                rag_results = await rag_service.get_answer(
                    project_id=project_id,
                    question=f"Provide comprehensive key facts, concepts, definitions, formulas, and important details about {topic}. Include specific examples and distinctions.",
                    selected_documents=selected_documents,
                    chat_history=[]
                )
                context = rag_results['answer']
            perf.stop("rag_context_fetch")
            
            # Generate flashcards using LLM with improved prompt
            prompt = f"""You are an expert educator creating high-quality study flashcards. Generate exactly {num_cards} flashcards for the topic: "{topic}"

Context from study documents:
{context if context else "No specific context provided. Use general knowledge about this topic."}

Requirements for excellent flashcards:
1. Each card tests ONE specific concept, fact, or definition
2. Front side: Clear, specific question or term (not vague or too broad)
3. Back side: Accurate, concise answer with key details (2-4 sentences max)
4. Cover different aspects: definitions, comparisons, applications, examples, cause-effect
5. Progress from basic concepts to more nuanced details
6. Use the document context to create accurate, specific cards (not generic)
7. Avoid yes/no questions - ask "what", "how", "why", "explain", "compare"

Return ONLY a valid JSON array (no markdown, no explanation):
[
  {{"front": "What is [specific concept]?", "back": "Detailed, accurate answer from the material."}},
  {{"front": "How does [process] work?", "back": "Step-by-step explanation with key details."}}
]

Generate exactly {num_cards} high-quality flashcards. Return ONLY the JSON array."""

            # Call LLM with more tokens for better quality
            perf.start("llm_response")
            response = await llm_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=3000
            )
            perf.stop("llm_response")
            
            # Parse the response to extract flashcards
            cards_data = self._parse_flashcards_response(response, num_cards)
            
            if not cards_data:
                raise Exception("Failed to generate flashcards from LLM response")
            
            # Create the flashcard set
            title = f"{topic} - Flashcards"
            description = f"AI-generated flashcards for {topic}"
            
            flashcard_set = await self.create_flashcard_set(
                user_id=user_id,
                project_id=project_id,
                title=title,
                topic=topic,
                description=description,
                cards=cards_data
            )
            
            logger.info(f"Generated {len(cards_data)} flashcards for topic: {topic}")
            perf.stop("flashcard_generation_total")
            perf.log_total(logger)
            return flashcard_set
        
        except Exception as e:
            logger.error(f"Error generating flashcards with AI: {e}")
            raise Exception(f"Failed to generate flashcards: {str(e)}")
    
    def _parse_flashcards_response(self, response: str, num_cards: int) -> List[Dict[str, str]]:
        """Parse LLM response into flashcard data with multiple fallback strategies."""
        # Strategy 1: Direct JSON array extraction
        try:
            # Clean markdown fences
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            # Try direct parse
            parsed = json.loads(text)
            if isinstance(parsed, list) and len(parsed) > 0:
                valid = [c for c in parsed if isinstance(c, dict) and 'front' in c and 'back' in c]
                if valid:
                    return valid[:num_cards]
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Strategy 2: Regex extraction of JSON array
        try:
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                cards_data = json.loads(json_match.group())
                if isinstance(cards_data, list):
                    valid = [c for c in cards_data if isinstance(c, dict) and 'front' in c and 'back' in c]
                    if valid:
                        return valid[:num_cards]
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Strategy 3: Line-by-line parsing for non-JSON formats
        cards_data = []
        lines = response.split('\n')
        current_front = ''
        
        for line in lines:
            line = line.strip()
            if line.startswith('FRONT:') or line.startswith('Q:') or line.startswith('Question:'):
                current_front = re.sub(r'^(FRONT:|Q:|Question:)\s*', '', line)
            elif (line.startswith('BACK:') or line.startswith('A:') or line.startswith('Answer:')) and current_front:
                back = re.sub(r'^(BACK:|A:|Answer:)\s*', '', line)
                cards_data.append({'front': current_front, 'back': back})
                current_front = ''
                if len(cards_data) >= num_cards:
                    break
        
        return cards_data[:num_cards]
