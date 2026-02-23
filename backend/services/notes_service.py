from typing import Dict, Any, List
from supabase import create_client, Client
from config.settings import settings
from utils.logger import logger
from uuid import uuid4
from datetime import datetime
from services.llm_service import llm_service
from services.embedding_service import embedding_service
from services.qdrant_service import qdrant_service

class NotesService:
    def __init__(self):
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )
    
    async def get_notes(self, project_id: str, user_id: str) -> Dict[str, Any]:
        """Get notes for a project"""
        try:
            response = self.client.table("notes").select("*").eq(
                "project_id", project_id
            ).eq("user_id", user_id).execute()
            
            if response.data:
                note = response.data[0]
                return {
                    "id": note["id"],
                    "project_id": note["project_id"],
                    "user_id": note["user_id"],
                    "content": note["content"],
                    "created_at": note["created_at"],
                    "updated_at": note["updated_at"]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting notes: {str(e)}")
            raise
    
    async def create_or_update_notes(
        self,
        project_id: str,
        user_id: str,
        content: str
    ) -> Dict[str, Any]:
        """Create or update notes for a project"""
        try:
            # Check if notes exist
            existing = await self.get_notes(project_id, user_id)
            
            if existing:
                # Update existing notes
                response = self.client.table("notes").update({
                    "content": content,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", existing["id"]).execute()
                
                logger.info(f"Updated notes for project {project_id}")
            else:
                # Create new notes
                note_id = str(uuid4())
                response = self.client.table("notes").insert({
                    "id": note_id,
                    "project_id": project_id,
                    "user_id": user_id,
                    "content": content
                }).execute()
                
                logger.info(f"Created notes for project {project_id}")
            
            return response.data[0] if response.data else {}
            
        except Exception as e:
            logger.error(f"Error creating/updating notes: {str(e)}")
            raise

    def _get_note_config(self, note_type: str, topic: str = None):
        """Return retrieval queries, system prompt, user prompt, and max_tokens per note type."""

        topic_label = f'"{topic}"' if topic else "the source material"
        topic_focus = f"\nFocus specifically on the topic: **{topic}**.\n" if topic else ""

        # ── Comprehensive Summary ──────────────────────────────────────
        if "Comprehensive" in note_type or "Summary" in note_type:
            queries = (
                [topic, f"detailed explanation of {topic}", f"examples and applications of {topic}",
                 f"background and context of {topic}", f"key theories and models for {topic}"]
                if topic else
                ["overview and introduction of the document", "main concepts theories and models",
                 "detailed explanations and examples", "conclusions results and implications",
                 "methodology and key findings", "definitions and important terms"]
            )
            system_prompt = (
                "You are an expert academic note-taker. You produce long-form, "
                "university-quality comprehensive study notes. Your output must be "
                "thorough, well-structured, and at least 1000-1500 words. "
                "You always include tables, diagrams described in text, real-world examples, "
                "and section summaries. Never cut corners or abbreviate content."
            )
            user_prompt = f"""Generate **Comprehensive Study Notes** from the following source material.
{topic_focus}
Source Material:
{{context}}

You MUST follow ALL of these formatting and content rules:

### Structure (use exactly these sections, adapt titles to the subject):
1. **Title & Overview** - A 3-5 sentence executive summary of what these notes cover.
2. **Key Concepts & Definitions** - Each concept gets its own subsection (### heading) with a clear definition, explanation, and an example. Present core definitions in a Markdown **table** with columns: | Term | Definition | Example |.
3. **Detailed Explanations** - Deep-dive into each major topic. Use subheadings (###), numbered steps for processes, and bullet points for supporting details. Include at least 2-3 paragraphs per major concept.
4. **Relationships & Connections** - A section explaining how the concepts relate to each other. Use a comparison table if there are contrasting ideas: | Aspect | Concept A | Concept B |.
5. **Real-World Examples & Applications** - At least 3 concrete examples showing how the theory applies in practice.
6. **Common Misconceptions** - List 3-5 things students often get wrong about this topic and the correct understanding.
7. **Summary & Key Takeaways** - Numbered list of the 8-12 most important points to remember.

### Formatting rules:
- Use proper Markdown: #, ##, ###, **bold**, *italic*, `code` where appropriate.
- Include at least **2 tables** (definitions table + comparison/relationship table).
- Use > blockquotes for important definitions or formulas.
- Total length: **minimum 1000 words**, aim for 1200-1500 words.
- Write in a clear, educational tone suitable for university students.

Respond ONLY with the Markdown notes content. Do not include meta-commentary."""
            max_tokens = 4500
            temperature = 0.5

        # ── Bullet Point Key Facts ─────────────────────────────────────
        elif "Bullet" in note_type or "Key Facts" in note_type:
            queries = (
                [topic, f"key facts about {topic}", f"important points of {topic}",
                 f"definitions related to {topic}"]
                if topic else
                ["important definitions and terms", "key facts and figures",
                 "critical points and takeaways", "main arguments and evidence",
                 "formulas equations and rules"]
            )
            system_prompt = (
                "You are a precise, detail-oriented study assistant. You produce "
                "well-organized bullet-point notes that capture every important fact, "
                "figure, definition, and relationship. You group bullets by logical "
                "categories and use hierarchy (main bullets and sub-bullets) for clarity."
            )
            user_prompt = f"""Generate **Bullet Point Key Facts** from the following source material.
{topic_focus}
Source Material:
{{context}}

You MUST follow ALL of these rules:

### Structure:
1. **Topic Header** - Bold title at the top.
2. **Categorized Sections** - Group facts under clear ## section headings (e.g., "## Definitions", "## Core Principles", "## Processes & Mechanisms", "## Key Figures & Data", "## Relationships & Comparisons").
3. Under each section, use hierarchical bullets:
   - **Main bullet** (- ) for primary facts — start each with a **bold key term** followed by a colon and the explanation.
     - *Sub-bullet* for supporting details, examples, or exceptions.
     - *Sub-bullet* for related formulas, dates, or figures.

### Content rules:
- Extract **every** important definition, fact, number, name, date, formula, and relationship from the source material.
- Each bullet must be a self-contained, meaningful fact — not vague summaries.
- If there are processes or sequences, use numbered sub-lists (1. 2. 3.) under the parent bullet.
- Include a final section: **## Quick-Review Checklist** — 8-10 yes/no self-test questions (e.g., "Can I explain X?").
- Aim for **40-60+ bullet points** total across all sections.
- Use **bold** for terms, *italic* for emphasis, and `code` for formulas or technical notation.

Respond ONLY with the Markdown bullet-point notes. Do not include meta-commentary."""
            max_tokens = 3500
            temperature = 0.4

        # ── Glossary of Terms ──────────────────────────────────────────
        elif "Glossary" in note_type:
            queries = (
                [topic, f"definitions and terminology of {topic}",
                 f"technical terms in {topic}", f"vocabulary and jargon for {topic}"]
                if topic else
                ["definitions and terminology", "technical terms and jargon",
                 "vocabulary and key words", "acronyms and abbreviations",
                 "specialized concepts and meanings"]
            )
            system_prompt = (
                "You are an expert lexicographer and subject-matter specialist. "
                "You produce thorough, well-organized glossaries with precise definitions, "
                "context, and usage examples. Every definition must be clear enough for "
                "a student encountering the term for the first time."
            )
            user_prompt = f"""Generate a **Glossary of Terms** from the following source material.
{topic_focus}
Source Material:
{{context}}

You MUST follow ALL of these rules:

### Structure:
1. **Title**: "## Glossary of Terms" (with topic subtitle if applicable).
2. **Main Glossary Table** — Present ALL terms in a Markdown table with these columns:
   | # | Term | Definition | Context / Example |
   |---|------|-----------|-------------------|
   Number each row sequentially. The Definition column must be 1-3 clear sentences. The Context column gives a usage example or explains when/where the term appears.

3. **Grouped Terminology** (after the table) — Organize the same terms into logical category groups (e.g., "### Process Terms", "### Measurement Terms", "### Theoretical Concepts") with a 1-sentence definition each. This helps students see which terms belong together.

4. **Acronyms & Abbreviations** — If any exist, list them in a separate small table:
   | Abbreviation | Full Form | Meaning |

5. **Relationships Between Terms** — A short paragraph or bullet list explaining how 3-5 key terms connect to or depend on each other.

### Content rules:
- Extract **every** technical term, concept name, proper noun, and specialized word from the source material.
- Aim for **at least 15-25 terms** (more if the material is terminology-heavy).
- Definitions must be precise and self-contained — a student should understand the term from the definition alone.
- Sort the main table **alphabetically** by Term.
- Use **bold** for the term when it first appears, *italic* for related terms referenced within definitions.

Respond ONLY with the Markdown glossary content. Do not include meta-commentary."""
            max_tokens = 3500
            temperature = 0.3

        # ── Exam Cheat Sheet ───────────────────────────────────────────
        elif "Cheat Sheet" in note_type or "Exam" in note_type:
            queries = (
                [topic, f"formulas and equations for {topic}", f"key rules and principles of {topic}",
                 f"common exam questions about {topic}", f"important facts to memorize for {topic}"]
                if topic else
                ["formulas equations and rules", "key definitions to memorize",
                 "important theorems and principles", "common mistakes and pitfalls",
                 "critical facts figures and dates", "step-by-step procedures and methods"]
            )
            system_prompt = (
                "You are an expert exam coach. You create dense, high-yield cheat sheets "
                "that pack the maximum amount of testable information into a compact format. "
                "You prioritize formulas, definitions, rules, exceptions, and mnemonics. "
                "Every line must be something that could appear on an exam."
            )
            user_prompt = f"""Generate an **Exam Cheat Sheet** from the following source material.
{topic_focus}
Source Material:
{{context}}

You MUST follow ALL of these rules:

### Structure (use these exact sections):
1. **## Must-Know Definitions** — The 8-12 most critical terms in a compact table:
   | Term | One-Line Definition |

2. **## Formulas & Equations** — Every formula, equation, or quantitative relationship. Present each as:
   > **Formula Name**: `formula here`
   > Where: variable = meaning, variable = meaning
   (If there are no mathematical formulas, use key rules/principles in the same format.)

3. **## Key Principles & Rules** — Numbered list of the core rules, laws, or principles. Each gets ONE line — be maximally concise.

4. **## Comparison Tables** — Side-by-side comparisons of easily confused concepts:
   | Feature | Concept A | Concept B |

5. **## Process Checklists** — Any step-by-step processes as numbered checklists.

6. **## Common Pitfalls & Traps** — 5-8 bullet points of mistakes examiners test for:
   - **Wrong**: [common misconception] → **Right**: [correct understanding]

7. **## Memory Aids** — 2-4 mnemonics, acronyms, or memory tricks to remember key sequences or lists.

8. **## Last-Minute Review** — The absolute top 10 facts to read 5 minutes before the exam, as a numbered list. Each must be one sentence.

### Formatting rules:
- Maximum density — no filler words, no long explanations.
- Use **bold** aggressively for key terms.
- Use `code formatting` for formulas and technical notation.
- Use > blockquotes for formulas and critical rules.
- Use tables wherever possible for compact presentation.
- This should fit on 2-3 printed pages — keep it tight and scannable.

Respond ONLY with the Markdown cheat sheet content. Do not include meta-commentary."""
            max_tokens = 3500
            temperature = 0.3

        # ── Fallback (unknown type) ────────────────────────────────────
        else:
            queries = (
                [topic, f"{note_type} about {topic}"]
                if topic else
                ["overview of the document", "main concepts and themes", note_type]
            )
            system_prompt = (
                "You are an expert academic note-taker who produces thorough, "
                "well-structured study notes with proper Markdown formatting."
            )
            user_prompt = f"""Generate **{note_type}** notes from the following source material.
{topic_focus}
Source Material:
{{context}}

Requirements:
- Use proper Markdown formatting with headers, bullet points, bold, and tables.
- Be thorough and comprehensive.
- Structure the content logically with clear sections.
- Include definitions, examples, and key relationships.
- Aim for at least 600-800 words.

Respond ONLY with the Markdown content."""
            max_tokens = 3000
            temperature = 0.5

        return {
            "queries": queries,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

    async def generate_notes(
        self,
        project_id: str,
        note_type: str,
        topic: str = None,
        selected_documents: List[str] = None
    ) -> str:
        """Generate notes using AI with type-specific prompts and retrieval strategies."""
        try:
            logger.info(f"Generating notes ({note_type}) for project {project_id}, topic: {topic}")

            # 1. Get type-specific configuration
            config = self._get_note_config(note_type, topic)

            # 2. Retrieve content with type-specific queries
            collection_name = f"project_{project_id}"
            all_hits = []
            seen_texts = set()

            for q in config["queries"]:
                embedding = await embedding_service.generate_embedding(q)
                results = await qdrant_service.search(
                    collection_name=collection_name,
                    query_vector=embedding,
                    limit=12,
                    filter_conditions={"document_ids": selected_documents} if selected_documents else None
                )
                for hit in results:
                    if hit["text"] not in seen_texts:
                        all_hits.append(hit)
                        seen_texts.add(hit["text"])

            if not all_hits:
                return "No content found to generate notes. Please ensure documents are uploaded and processed."

            # Combine content — use more chunks for comprehensive notes
            chunk_limit = 25 if "Comprehensive" in note_type or "Summary" in note_type else 20
            context = "\n\n".join([hit["text"] for hit in all_hits[:chunk_limit]])

            # 3. Build the prompt with context
            user_prompt = config["user_prompt"].replace("{context}", context)

            # 4. Send to LLM with system message for better instruction following
            messages = [
                {"role": "system", "content": config["system_prompt"]},
                {"role": "user", "content": user_prompt}
            ]
            response = await llm_service.chat_completion(
                messages,
                temperature=config["temperature"],
                max_tokens=config["max_tokens"]
            )

            return response

        except Exception as e:
            logger.error(f"Error generating notes: {str(e)}")
            raise

notes_service = NotesService()
