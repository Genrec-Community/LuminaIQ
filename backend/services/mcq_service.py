import json
import asyncio
from typing import List, Dict, Any, Union
from services.embedding_service import embedding_service
from services.qdrant_service import qdrant_service
from services.llm_service import llm_service
from db.client import get_supabase_client, async_db
from config.settings import settings
from utils.logger import logger
from uuid import uuid4


# Strong refs to fire-and-forget tasks so they aren't garbage-collected
_background_tasks: set = set()


class MCQService:
    def __init__(self):
        self.client = get_supabase_client()

    async def generate_document_topics(
        self, project_id: str, document_id: str
    ) -> List[str]:
        """Extract a chapter-grouped topic outline covering the whole document."""
        from services.topic_outline_service import topic_outline_service

        try:
            return await topic_outline_service.generate_outline(project_id, document_id)
        except Exception as e:
            logger.error(f"Error generating doc topics: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return []

    async def get_topics(self, project_id: str) -> Dict[str, Any]:
        """
        Topics for the project in learning order (the same order as the
        Learning Path), plus per-document lists, chapter outlines and
        per-topic metadata (level, chapter, prerequisites).
        """
        from services.knowledge_graph_service import knowledge_graph
        from services.topic_outline_service import topic_outline_service

        try:
            documents = await knowledge_graph.load_project_documents(project_id)

            # Lazy generation for documents that have no topics yet
            missing = [d for d in documents if not d.get("topics")]
            if missing:
                logger.info(f"Generating topics for {len(missing)} documents...")
                results = await asyncio.gather(
                    *(self.generate_document_topics(project_id, d["id"]) for d in missing)
                )
                for d, topics in zip(missing, results):
                    d["topics"] = topics

            # Older documents: group existing topics into chapters (background, once)
            for d in documents:
                if d.get("topics") and "topic_outline" in d and not d.get("topic_outline"):
                    task = asyncio.create_task(topic_outline_service.organize_existing(d))
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)

            path = await knowledge_graph.generate_learning_path(project_id, documents=documents)
            ordered = [p["topic"] for p in path]

            by_doc = {}
            for d in documents:
                doc_topics = set(d.get("topics") or [])
                by_doc[d["id"]] = [t for t in ordered if t in doc_topics]

            meta = {
                p["topic"]: {
                    "order": p["order"],
                    "level": p["level"],
                    "chapter": p.get("chapter"),
                    "foundation": p["foundation"],
                    "prerequisites": p["prerequisites"][:3],
                    "unlocks": len(p["unlocks"]),
                }
                for p in path
            }

            # Build the knowledge graph once if it doesn't exist yet (background)
            if len(ordered) >= 3:
                try:
                    stats = await knowledge_graph.get_graph_stats(project_id)
                    if stats.get("total_edges", 0) == 0:
                        task = asyncio.create_task(
                            knowledge_graph.build_graph_from_topics(project_id, ordered)
                        )
                        _background_tasks.add(task)
                        task.add_done_callback(_background_tasks.discard)
                        logger.info(f"Triggered knowledge graph build for project {project_id}")
                except Exception as kg_err:
                    logger.warning(f"Knowledge graph build skipped: {kg_err}")

            return {
                "all": ordered,
                "by_doc": by_doc,
                "outline": {d["id"]: d.get("topic_outline") or [] for d in documents},
                "meta": meta,
            }

        except Exception as e:
            logger.error(f"Error extracting topics: {str(e)}")
            return {"all": [], "by_doc": {}, "outline": {}, "meta": {}}

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
        try:
            # 1. Get relevant content for the chapter/topic
            logger.info(
                f"Retrieving content for topic: {topic if topic else 'General'}"
            )
            # Increased chunks for better context
            content = await self._get_context_content(
                project_id, topic, num_chunks=15, selected_documents=selected_documents
            )

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
            response = await llm_service.chat_completion(
                messages, temperature=0.7, max_tokens=6000, light=True
            )

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
        """Retrieve relevant content — parallel multi-query retrieval (no LLM expansion)."""
        try:
            collection_name = f"project_{project_id}"
            filter_conds = {"document_ids": selected_documents} if selected_documents else None

            # Build query variants without LLM (saves 2-3s per call)
            if topic:
                queries = [
                    topic,
                    f"definition and explanation of {topic}",
                    f"examples and applications of {topic}",
                    f"key concepts in {topic}",
                ]
            else:
                queries = ["important concepts", "key definitions", "main topics", "summary"]

            limit_per_query = max(3, num_chunks // len(queries))

            # Run ALL embedding + qdrant searches in parallel
            async def _search_one(q: str):
                emb = await embedding_service.generate_embedding(q)
                return await qdrant_service.search(
                    collection_name=collection_name,
                    query_vector=emb,
                    limit=limit_per_query,
                    filter_conditions=filter_conds,
                )

            results_list = await asyncio.gather(*[_search_one(q) for q in queries])

            all_hits = []
            seen_texts = set()
            for results in results_list:
                for hit in results:
                    if hit["text"] not in seen_texts:
                        all_hits.append(hit)
                        seen_texts.add(hit["text"])

            final_chunks = [hit["text"] for hit in all_hits][:num_chunks]
            return "\n\n".join(final_chunks)

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
            # Fetch everything in ONE query (no N+1)
            response = await async_db(lambda:
                self.client.table("mcq_tests")
                .select("id, project_id, chapter_name, created_at, questions")
                .eq("project_id", project_id)
                .order("created_at", desc=True)
                .execute()
            )
            tests = response.data or []
            for test in tests:
                try:
                    qs = test.pop("questions", None)
                    test["question_count"] = len(json.loads(qs)) if qs else 0
                except (json.JSONDecodeError, TypeError):
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
