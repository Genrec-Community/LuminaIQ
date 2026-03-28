import json
import asyncio
from typing import List, Dict, Any, Union
from services.embedding_service import embedding_service
from services.qdrant_service import qdrant_service
from services.llm_service import llm_service
from db.client import get_supabase_client, async_db
from config.settings import settings
from utils.logger import logger
from utils.performance import PerformanceTracker
from uuid import uuid4


class MCQService:
    def __init__(self):
        self.client = get_supabase_client()

    async def generate_document_topics(
        self, project_id: str, document_id: str
    ) -> List[str]:
        """Generate comprehensive topics for a single document"""
        try:
            collection_name = f"project_{project_id}"
            chunks = await qdrant_service.get_initial_chunks(
                collection_name=collection_name,
                document_id=document_id,
                limit=30,  # Increased to capture more content for topic extraction
            )

            if not chunks:
                logger.warning(f"No chunks found for document {document_id}")
                return []

            text = "\n".join(chunks)

            # DIAGNOSTIC: Log text sample before sending to LLM
            logger.debug(f"====== EXTRACTED TEXT SAMPLE ======\n{text[:1000] if text else 'EMPTY TEXT'}\n====================================")
            logger.info(f"TEXT LENGTH: {len(text)} chars")
            logger.info(f"CHUNK COUNT: {len(chunks)} chunks")

            system_prompt = """You are an expert curriculum analyst. Analyze this educational content and extract ALL learning topics.

INSTRUCTIONS:
1. Extract EVERY distinct topic, concept, chapter, or learning objective
2. Include main topics AND subtopics (e.g., "Machine Learning" AND "Neural Networks")
3. Use clear, educational topic names (not chapter numbers like "Chapter 1")
4. Ignore non-content pages: Table of Contents, Index, Copyright, Acknowledgements
5. Topics should be specific enough to create quiz questions about
6. Target 15-30 topics for comprehensive coverage

EXAMPLES of good topics:
- "Introduction to Python Programming"
- "Object-Oriented Programming Concepts"
- "Exception Handling in Python"
- "Working with Files and I/O"

Return ONLY a valid JSON array of topic strings:
["Topic 1", "Topic 2", "Topic 3"]"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"CONTENT:\n{text[:14000]}"}
            ]
            response = await llm_service.chat_completion(messages, temperature=0.3, max_tokens=2000)
            
            # DIAGNOSTIC: Log raw LLM output
            logger.debug(f"====== RAW LLM OUTPUT ======\n{response}\n===========================")
            if not response:
                logger.error("LLM returned empty response for topic generation")
                return []

            topics = []
            start = response.find("[")
            end = response.rfind("]") + 1
            if start != -1 and end > start:
                try:
                    loaded = json.loads(response[start:end])
                    if isinstance(loaded, list):
                        # Clean and deduplicate topics
                        seen = set()
                        for t in loaded:
                            if isinstance(t, str):
                                clean_topic = t.strip()
                                if clean_topic and clean_topic.lower() not in seen:
                                    topics.append(clean_topic)
                                    seen.add(clean_topic.lower())
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse topics JSON: {e}")
                    # FALLBACK: Try to extract topics from raw response text
                    logger.warning("FALLBACK: Trying to extract topics from raw text...")
                    import re
                    # Look for quoted strings in the response
                    matches = re.findall(r'"([^"]+)"', response)
                    for m in matches:
                        clean = m.strip()
                        if clean and len(clean) > 3 and clean.lower() not in seen:
                            topics.append(clean)
                            seen.add(clean.lower())
                    if topics:
                        logger.info(f"FALLBACK: Extracted {len(topics)} topics from raw text")

            # Save to document
            if topics:
                await async_db(lambda: self.client.table("documents").update({"topics": topics}).eq(
                    "id", document_id
                ).execute())
                logger.info(f"Generated {len(topics)} topics for doc {document_id}")
                
                # Invalidate document metadata cache when topics are updated
                try:
                    from core.redis_manager import get_redis_manager
                    redis_manager = get_redis_manager()
                    cache_key = f"doc:{document_id}"
                    await redis_manager.delete(cache_key)
                    logger.debug(f"Invalidated document cache for {document_id} after topic update")
                    
                    # Also invalidate project documents cache
                    project_cache_key = f"docs:{project_id}"
                    await redis_manager.delete(project_cache_key)
                    logger.debug(f"Invalidated project documents cache for {project_id}")
                except Exception as cache_err:
                    logger.warning(f"Failed to invalidate document cache after topic update: {cache_err}")
            else:
                logger.warning(f"No topics generated for doc {document_id}")

            return topics
        except Exception as e:
            logger.error(f"Error generating doc topics: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return []

    async def get_topics(self, project_id: str) -> Dict[str, Any]:
        """Get aggregated topics AND per-document topics. Also triggers knowledge graph building."""
        try:
            # Get all docs with their topics
            response = await async_db(
                lambda: self.client.table("documents")
                .select("id, topics")
                .eq("project_id", project_id)
                .eq("upload_status", "completed")
                .execute()
            )
            documents = response.data or []

            all_topics = set()
            by_doc = {}
            docs_needing_generation = []

            for doc in documents:
                doc_topics = doc.get("topics") or []
                by_doc[doc["id"]] = doc_topics

                if doc_topics:
                    for t in doc_topics:
                        all_topics.add(t)
                else:
                    docs_needing_generation.append(doc["id"])

            # Lazy generation for docs missing topics
            if docs_needing_generation:
                logger.info(
                    f"Generating topics for {len(docs_needing_generation)} documents..."
                )
                tasks = [
                    self.generate_document_topics(project_id, doc_id)
                    for doc_id in docs_needing_generation
                ]
                # Run concurrently
                results = await asyncio.gather(*tasks)

                # Update our local maps with results
                for i, doc_id in enumerate(docs_needing_generation):
                    t_list = results[i]
                    by_doc[doc_id] = t_list
                    for t in t_list:
                        all_topics.add(t)

            # Auto-build knowledge graph if we have enough topics (background task)
            sorted_topics = sorted(list(all_topics))
            if len(sorted_topics) >= 3:
                try:
                    from services.knowledge_graph_service import knowledge_graph

                    # Check if graph already exists
                    stats = await knowledge_graph.get_graph_stats(project_id)
                    if stats.get("total_edges", 0) == 0:
                        # Build graph in background (don't await, fire and forget)
                        asyncio.create_task(
                            knowledge_graph.build_graph_from_topics(
                                project_id, sorted_topics
                            )
                        )
                        logger.info(
                            f"Triggered knowledge graph build for project {project_id}"
                        )
                except Exception as kg_err:
                    logger.warning(f"Knowledge graph build skipped: {kg_err}")

            return {"all": sorted_topics, "by_doc": by_doc}

        except Exception as e:
            logger.error(f"Error extracting topics: {str(e)}")
            return {"all": [], "by_doc": {}}

    async def generate_mcq(
        self,
        project_id: str,
        topic: str = None,
        num_questions: int = 5,
        selected_documents: List[str] = None,
        difficulty: str = "medium",
    ) -> Dict[str, Any]:
        """Generate MCQ test from project documents

        Args:
            difficulty: 'easy', 'medium', or 'hard'
        """
        perf = PerformanceTracker()
        perf.start("mcq_generation_total")
        try:
            # 1. Get relevant content for the chapter/topic
            logger.info(
                f"Retrieving content for topic: {topic if topic else 'General'}"
            )
            # Increased chunks for better context
            perf.start("qdrant_search")
            content = await self._get_context_content(
                project_id, topic, num_chunks=15, selected_documents=selected_documents
            )
            perf.stop("qdrant_search")

            if not content:
                # Fallback if no specific content found
                logger.warning(
                    "No specific content found, generating generic questions"
                )

            # 2. Generate MCQs using LLM with difficulty modifier
            prompt_topic = f"Topic: {topic}" if topic else "Topic: General Review"

            # Difficulty-specific instructions
            difficulty_instructions = {
                "easy": """
- Questions should test basic recall and understanding.
- Options should be clearly distinguishable.
- Avoid trick questions or subtle distinctions.
- Focus on fundamental concepts and definitions.""",
                "medium": """
- Questions should test understanding and application.
- Include some questions requiring comparison or analysis.
- Options may have subtle differences but should be fair.
- Balance between recall and critical thinking.""",
                "hard": """
- Questions should test deep understanding, analysis, and critical thinking.
- Include questions that require synthesizing multiple concepts.
- Options may be nuanced and require careful consideration.
- Include scenario-based and application questions.
- Some questions may require multi-step reasoning.""",
            }

            diff_instruction = difficulty_instructions.get(
                difficulty, difficulty_instructions["medium"]
            )

            prompt = f"""Based on the following educational content, generate {num_questions} multiple-choice questions.
{prompt_topic}
Difficulty Level: {difficulty.upper()}

Content:
{content}

Requirements:
{diff_instruction}
- Each question should have 4 options (A, B, C, D).
- Only one option should be correct.
- **Use Markdown** for the question text and explanation (e.g., bold keywords, code blocks if relevant).
- Include a clear and detailed explanation for the correct answer.

Format your response as a **JSON array** with this structure:
[
  {{
    "question": "**Question text** here?",
    "options": [
      {{"option": "A", "text": "First option"}},
      {{"option": "B", "text": "Second option"}},
      {{"option": "C", "text": "Third option"}},
      {{"option": "D", "text": "Fourth option"}}
    ],
    "correct_answer": "A",
    "explanation": "Explanation of why **A** is correct..."
  }}
]

Respond ONLY with the valid JSON array. Do not add any markdown formatting (like ```json) around the response."""

            messages = [{"role": "user", "content": prompt}]
            perf.start("llm_response")
            response = await llm_service.chat_completion(
                messages, temperature=0.7, max_tokens=3000
            )
            perf.stop("llm_response")

            # 3. Parse response
            questions = self._parse_mcq_response(response)

            if not questions:
                raise Exception("Failed to parse MCQ questions from response")

            # 4. Store in database
            test_id = str(uuid4())
            await async_db(lambda: self.client.table("mcq_tests").insert(
                {
                    "id": test_id,
                    "project_id": project_id,
                    "chapter_name": topic if topic else "General Quiz",
                    "questions": json.dumps(questions),
                }
            ).execute())

            logger.info(f"Created MCQ test with ID: {test_id}")
            
            perf.stop("mcq_generation_total")
            perf.log_total(logger)

            return {"test_id": test_id, "topic": topic, "questions": questions}

        except Exception as e:
            logger.error(f"Error generating MCQ: {str(e)}")
            raise

    async def _get_context_content(
        self,
        project_id: str,
        topic: str = None,
        num_chunks: int = 15,
        selected_documents: List[str] = None,
    ) -> str:
        """Retrieve relevant content using Query Expansion (Multi-Query)"""
        try:
            collection_name = f"project_{project_id}"

            # 1. Generate variations of the query (Query Expansion)
            # If a topic is provided, we ask the LLM to generate sub-topics or related questions to broaden search.
            queries = (
                [topic]
                if topic
                else ["important concepts", "summary", "key definitions"]
            )

            if topic:
                expansion_prompt = f"""You are an AI assistant helping to search a vector database. 
Generate 3 alternative search queries or related sub-topics for the topic: "{topic}" 
to ensure we find all relevant information in an educational textbook.
Return only the 3 queries separated by newlines."""

                try:
                    expansion_response = await llm_service.chat_completion(
                        [{"role": "user", "content": expansion_prompt}], temperature=0.7
                    )
                    queries.extend(
                        [q.strip() for q in expansion_response.split("\n") if q.strip()]
                    )
                except Exception as e:
                    logger.warning(f"Query expansion failed: {e}")

            logger.info(f"Generated {len(queries)} search queries: {queries}")

            # 2. Perform Search for each query
            all_hits = []
            seen_texts = set()

            # Distribute the chunk limit across queries, but ensure at least 3 per query
            limit_per_query = max(3, num_chunks // len(queries))

            for query_text in queries:
                query_embedding = await embedding_service.generate_embedding(query_text)

                results = await qdrant_service.search(
                    collection_name=collection_name,
                    query_vector=query_embedding,
                    limit=limit_per_query,
                    filter_conditions={"document_ids": selected_documents}
                    if selected_documents
                    else None,
                )

                for hit in results:
                    if hit["text"] not in seen_texts:
                        all_hits.append(hit)
                        seen_texts.add(hit["text"])

            # 3. Sort and Deduplicate (Implicitly done by set, but maybe we want to re-rank?
            # For now, simple concatenation is sufficient for context window)

            # Limit total content size roughly
            final_chunks = [hit["text"] for hit in all_hits][:num_chunks]

            content = "\n\n".join(final_chunks)
            return content

        except Exception as e:
            logger.error(f"Error retrieving context content: {str(e)}")
            return ""

    def _parse_mcq_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response to extract MCQ questions"""
        try:
            # Try to find JSON array in response
            start = response.find("[")
            end = response.rfind("]") + 1

            if start == -1 or end == 0:
                logger.warning("No JSON array found in response")
                return []

            json_str = response[start:end]
            questions = json.loads(json_str)

            # Validate structure
            for q in questions:
                if not all(
                    key in q
                    for key in ["question", "options", "correct_answer", "explanation"]
                ):
                    logger.warning("Invalid question structure")
                    return []

            return questions

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            return []

    async def submit_test(
        self, test_id: str, answers: Dict[int, str]
    ) -> Dict[str, Any]:
        """Evaluate submitted test answers"""
        try:
            # 1. Get test from database
            response = await async_db(lambda: 
                self.client.table("mcq_tests").select("*").eq("id", test_id).execute()
            )

            if not response.data:
                raise Exception("Test not found")

            test = response.data[0]
            questions = json.loads(test["questions"])

            # 2. Evaluate answers
            score = 0
            total = len(questions)
            feedback = []

            for i, question in enumerate(questions):
                user_answer = answers.get(i)
                correct_answer = question["correct_answer"]

                is_correct = user_answer == correct_answer
                if is_correct:
                    score += 1

                feedback.append(
                    {
                        "question_number": i + 1,
                        "question": question["question"],
                        "user_answer": user_answer,
                        "correct_answer": correct_answer,
                        "is_correct": is_correct,
                        "explanation": question["explanation"],
                    }
                )

            percentage = (score / total * 100) if total > 0 else 0

            return {
                "score": score,
                "total": total,
                "percentage": round(percentage, 2),
                "feedback": feedback,
            }

        except Exception as e:
            logger.error(f"Error submitting test: {str(e)}")
            raise


    async def get_saved_tests(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all saved MCQ tests for a project"""
        try:
            response = await async_db(lambda: 
                self.client.table("mcq_tests")
                .select("id, project_id, chapter_name, created_at")
                .eq("project_id", project_id)
                .order("created_at", desc=True)
                .execute()
            )
            tests = response.data or []
            # Add question count from stored JSON
            for test in tests:
                # Fetch question count separately to keep listing lightweight
                q_response = await async_db(lambda: 
                    self.client.table("mcq_tests")
                    .select("questions")
                    .eq("id", test["id"])
                    .execute()
                )
                if q_response.data and q_response.data[0].get("questions"):
                    try:
                        questions = json.loads(q_response.data[0]["questions"])
                        test["question_count"] = len(questions)
                    except (json.JSONDecodeError, TypeError):
                        test["question_count"] = 0
                else:
                    test["question_count"] = 0
            return tests
        except Exception as e:
            logger.error(f"Error getting saved MCQ tests: {str(e)}")
            raise

    async def get_saved_test(self, test_id: str) -> Dict[str, Any]:
        """Get a specific saved MCQ test with full questions"""
        try:
            response = await async_db(lambda: 
                self.client.table("mcq_tests")
                .select("*")
                .eq("id", test_id)
                .execute()
            )
            if not response.data:
                raise Exception("Test not found")

            test = response.data[0]
            if test.get("questions") and isinstance(test["questions"], str):
                test["questions"] = json.loads(test["questions"])
            return test
        except Exception as e:
            logger.error(f"Error getting saved MCQ test: {str(e)}")
            raise

    async def delete_saved_test(self, test_id: str):
        """Delete a saved MCQ test"""
        try:
            response = await async_db(lambda: 
                self.client.table("mcq_tests")
                .delete()
                .eq("id", test_id)
                .execute()
            )
            if not response.data:
                raise Exception("Test not found")
            logger.info(f"Deleted MCQ test {test_id}")
        except Exception as e:
            logger.error(f"Error deleting MCQ test: {str(e)}")
            raise


mcq_service = MCQService()
