from typing import List, Dict, Any, Optional
from db.client import get_supabase_client
from services.llm_service import LLMService
from services.rag_service import RAGService
from utils.logger import logger
import json

class MindmapService:
    def __init__(self):
        self.supabase = get_supabase_client()
        self.llm_service = LLMService()
        self.rag_service = RAGService()
    
    async def get_mindmaps(self, user_id: str, project_id: str) -> List[Dict[str, Any]]:
        """Get all mindmaps for a project"""
        try:
            response = self.supabase.table('mindmaps') \
                .select('*') \
                .eq('user_id', user_id) \
                .eq('project_id', project_id) \
                .order('created_at', desc=True) \
                .execute()
            
            results = response.data or []
            # Parse data from JSON string to dict for each mindmap
            for item in results:
                if item.get('data') and isinstance(item['data'], str):
                    try:
                        item['data'] = json.loads(item['data'])
                    except (json.JSONDecodeError, TypeError):
                        item['data'] = {"nodes": [], "edges": []}
            
            return results
        
        except Exception as e:
            logger.error(f"Error fetching mindmaps: {e}")
            raise Exception(f"Failed to fetch mindmaps: {str(e)}")
    
    async def generate_mindmap(
        self,
        user_id: str,
        project_id: str,
        title: str,
        topic: str,
        selected_documents: List[str]
    ) -> Dict[str, Any]:
        """Generate a new mindmap using LLM"""
        try:
            # Get relevant context from documents
            context = ""
            if selected_documents:
                rag_results = await self.rag_service.get_answer(
                    project_id=project_id,
                    question=f"Explain {topic} and its key concepts, relationships, and subtopics in detail",
                    selected_documents=selected_documents,
                    chat_history=[]
                )
                context = rag_results['answer']
            
            # Generate mindmap structure using LLM
            prompt = f"""You are a knowledge mapping expert. Generate a detailed, well-structured mindmap for the topic: "{topic}"

Context from study documents:
{context if context else "No specific context provided. Use general knowledge about this topic."}

Requirements:
1. Central node: The main topic
2. 4-7 main branches: Key concepts/themes directly related to the central topic
3. 2-4 sub-branches per main branch: Specific details, examples, or subtopics
4. Each label should be concise (2-6 words), descriptive, and educational
5. Use the document context to make labels specific and accurate, not generic

Return ONLY a valid JSON object (no markdown, no explanation) with this exact structure:
{{
  "nodes": [
    {{"id": "1", "label": "{topic}", "level": 0}},
    {{"id": "2", "label": "Main Concept A", "level": 1, "parent": "1"}},
    {{"id": "3", "label": "Detail of A", "level": 2, "parent": "2"}},
    {{"id": "4", "label": "Main Concept B", "level": 1, "parent": "1"}},
    {{"id": "5", "label": "Detail of B", "level": 2, "parent": "4"}}
  ],
  "edges": [
    {{"from": "1", "to": "2"}},
    {{"from": "2", "to": "3"}},
    {{"from": "1", "to": "4"}},
    {{"from": "4", "to": "5"}}
  ]
}}

Generate a comprehensive mindmap with at least 15-25 nodes total. Return ONLY the JSON."""

            llm_response = await self.llm_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000
            )
            
            # Parse the LLM response
            try:
                # Clean the response
                response_text = llm_response.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                mindmap_data = json.loads(response_text)
                
                # Validate structure
                if 'nodes' not in mindmap_data or 'edges' not in mindmap_data:
                    raise ValueError("Invalid mindmap structure - missing nodes or edges")
                
                # Ensure all nodes have required fields
                for node in mindmap_data['nodes']:
                    if 'id' not in node or 'label' not in node:
                        raise ValueError("Invalid node - missing id or label")
                    node.setdefault('level', 0)
                
                # Validate edges reference existing node IDs
                node_ids = {n['id'] for n in mindmap_data['nodes']}
                mindmap_data['edges'] = [
                    e for e in mindmap_data['edges']
                    if e.get('from') in node_ids and e.get('to') in node_ids
                ]
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse LLM response: {e}")
                logger.warning(f"Response text (first 500 chars): {response_text[:500]}")
                # Fallback to a meaningful structure
                mindmap_data = self._build_fallback_mindmap(topic, context)
            
            # Save to database
            node_count = len(mindmap_data.get('nodes', []))
            edge_count = len(mindmap_data.get('edges', []))
            
            mindmap_record = {
                'user_id': user_id,
                'project_id': project_id,
                'title': title,
                'topic': topic,
                'data': json.dumps(mindmap_data),
                'document_ids': selected_documents,
                'node_count': node_count,
                'edge_count': edge_count,
            }
            
            response = self.supabase.table('mindmaps') \
                .insert(mindmap_record) \
                .execute()
            
            if not response.data:
                raise Exception("Failed to save mindmap")
            
            result = response.data[0]
            # Parse data back to dict for response
            if isinstance(result.get('data'), str):
                result['data'] = json.loads(result['data'])
            
            logger.info(f"Generated mindmap {result['id']} for topic: {topic} ({node_count} nodes, {edge_count} edges)")
            return result
        
        except Exception as e:
            logger.error(f"Error generating mindmap: {e}")
            raise Exception(f"Failed to generate mindmap: {str(e)}")
    
    def _build_fallback_mindmap(self, topic: str, context: str = "") -> Dict[str, Any]:
        """Build a basic fallback mindmap when LLM parsing fails."""
        # Extract some keywords from context if available
        keywords = []
        if context:
            words = context.split()
            # Simple keyword extraction: capitalize words that appear frequently
            from collections import Counter
            word_counts = Counter(w.lower().strip('.,;:!?()[]{}') for w in words if len(w) > 4)
            keywords = [w for w, _ in word_counts.most_common(6) if w.lower() != topic.lower()]
        
        if len(keywords) < 3:
            keywords = ["Key Concept 1", "Key Concept 2", "Key Concept 3", "Key Concept 4"]
        
        nodes = [{"id": "1", "label": topic, "level": 0}]
        edges = []
        
        for i, kw in enumerate(keywords[:6], start=2):
            nodes.append({"id": str(i), "label": kw.title(), "level": 1, "parent": "1"})
            edges.append({"from": "1", "to": str(i)})
        
        return {"nodes": nodes, "edges": edges}
    
    async def get_mindmap(self, user_id: str, mindmap_id: str) -> Dict[str, Any]:
        """Get a specific mindmap"""
        try:
            response = self.supabase.table('mindmaps') \
                .select('*') \
                .eq('id', mindmap_id) \
                .eq('user_id', user_id) \
                .execute()
            
            if not response.data:
                raise Exception("Mindmap not found or unauthorized")
            
            result = response.data[0]
            # Parse data from JSON string to dict
            if isinstance(result.get('data'), str):
                result['data'] = json.loads(result['data'])
            
            return result
        
        except Exception as e:
            logger.error(f"Error fetching mindmap: {e}")
            raise Exception(f"Failed to fetch mindmap: {str(e)}")
    
    async def update_mindmap(
        self,
        user_id: str,
        mindmap_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a mindmap"""
        try:
            # Convert data dict to JSON string if present
            if 'data' in updates and isinstance(updates['data'], dict):
                updates['data'] = json.dumps(updates['data'])
            
            response = self.supabase.table('mindmaps') \
                .update(updates) \
                .eq('id', mindmap_id) \
                .eq('user_id', user_id) \
                .execute()
            
            if not response.data:
                raise Exception("Mindmap not found or unauthorized")
            
            result = response.data[0]
            # Parse data back to dict
            if isinstance(result.get('data'), str):
                result['data'] = json.loads(result['data'])
            
            return result
        
        except Exception as e:
            logger.error(f"Error updating mindmap: {e}")
            raise Exception(f"Failed to update mindmap: {str(e)}")
    
    async def delete_mindmap(self, user_id: str, mindmap_id: str):
        """Delete a mindmap"""
        try:
            response = self.supabase.table('mindmaps') \
                .delete() \
                .eq('id', mindmap_id) \
                .eq('user_id', user_id) \
                .execute()
            
            if not response.data:
                raise Exception("Mindmap not found or unauthorized")
            
            logger.info(f"Deleted mindmap {mindmap_id}")
        
        except Exception as e:
            logger.error(f"Error deleting mindmap: {e}")
            raise Exception(f"Failed to delete mindmap: {str(e)}")
