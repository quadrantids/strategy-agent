"""
Context Engine — Qdrant + multilingual-e5-large vector search + AI curation.

1. Chunks documents with enriched metadata prepended to embedding text
2. Stores in Qdrant local mode (no Docker)
3. At query time: vector search → AI curator selects best chunks → formatted context
"""

import os
import re
import json
import glob

VECTOR_DB_PATH = "vector_db"
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
CLASS_NOTES_FILE = "class_notes.txt"
COMPANIES_DIR = "companies"
ARTICLES_DIR = "articles"

# Chunking params (Miradouro-style)
MIN_CHUNK_SIZE = 100
MAX_CHUNK_SIZE = 1200
OVERLAP = 100


def _get_client():
    from qdrant_client import QdrantClient
    client = QdrantClient(path=VECTOR_DB_PATH)
    client.set_model(EMBEDDING_MODEL)
    return client


# ── Chunking with enriched text ──────────────────────────

def _enrich_text(text, source, section):
    """Prepend source/section context so the embedding captures semantics."""
    prefix = ""
    if source == "class_notes":
        prefix = f"[Strategy MBA Class Notes — Professor Luís Filipe Reis] Section: {section}\n\n"
    elif source.startswith("company:"):
        company = source.replace("company:", "")
        prefix = f"[Company: {company.upper()}] Section: {section}\n\n"
    else:
        prefix = f"[{source}] {section}\n\n"
    return prefix + text


def chunk_by_sections(text, source="unknown"):
    """Split text by section headers for class notes."""
    pattern = r'\n(?=#{1,4} |\d+\.\d+)'
    sections = re.split(pattern, text)

    chunks = []
    for section in sections:
        section = section.strip()
        if len(section) < MIN_CHUNK_SIZE:
            if chunks:
                chunks[-1]["raw_text"] += "\n\n" + section
            continue

        header = section.split("\n")[0].strip("# ").strip()

        if len(section) > MAX_CHUNK_SIZE:
            paragraphs = section.split("\n\n")
            current = ""
            for para in paragraphs:
                if len(current) + len(para) > MAX_CHUNK_SIZE and len(current) >= MIN_CHUNK_SIZE:
                    enriched = _enrich_text(current.strip(), source, header)
                    chunks.append({
                        "document": enriched,
                        "raw_text": current.strip(),
                        "metadata": {"source": source, "section": header},
                    })
                    current = f"### {header} (continued)\n\n{para}\n\n"
                else:
                    current += para + "\n\n"
            if len(current.strip()) >= MIN_CHUNK_SIZE:
                enriched = _enrich_text(current.strip(), source, header)
                chunks.append({
                    "document": enriched,
                    "raw_text": current.strip(),
                    "metadata": {"source": source, "section": header},
                })
        else:
            enriched = _enrich_text(section, source, header)
            chunks.append({
                "document": enriched,
                "raw_text": section,
                "metadata": {"source": source, "section": header},
            })

    return chunks


def chunk_markdown(text, source="unknown"):
    """Split markdown by ## headers with enriched embeddings."""
    sections = re.split(r'\n(?=## )', text)
    chunks = []

    company_name = source.replace("-", " ").title()

    for section in sections:
        section = section.strip()
        if len(section) < MIN_CHUNK_SIZE:
            if chunks:
                chunks[-1]["raw_text"] += "\n\n" + section
            continue

        header = section.split("\n")[0].strip("# ").strip()

        if len(section) > MAX_CHUNK_SIZE:
            paragraphs = section.split("\n\n")
            current = ""
            for para in paragraphs:
                if len(current) + len(para) > MAX_CHUNK_SIZE and len(current) >= MIN_CHUNK_SIZE:
                    enriched = _enrich_text(current.strip(), f"company:{company_name}", header)
                    chunks.append({
                        "document": enriched,
                        "raw_text": current.strip(),
                        "metadata": {"source": source, "section": header},
                    })
                    current = f"### {header} (continued)\n\n{para}\n\n"
                else:
                    current += para + "\n\n"
            if len(current.strip()) >= MIN_CHUNK_SIZE:
                enriched = _enrich_text(current.strip(), f"company:{company_name}", header)
                chunks.append({
                    "document": enriched,
                    "raw_text": current.strip(),
                    "metadata": {"source": source, "section": header},
                })
        else:
            enriched = _enrich_text(section, f"company:{company_name}", header)
            chunks.append({
                "document": enriched,
                "raw_text": section,
                "metadata": {"source": source, "section": header},
            })

    return chunks


# ── Index building ───────────────────────────────────────

def build_index():
    """Build the Qdrant vector database from class notes + company files."""
    import shutil
    if os.path.exists(VECTOR_DB_PATH):
        shutil.rmtree(VECTOR_DB_PATH)

    client = _get_client()

    # 1. Class notes
    if os.path.exists(CLASS_NOTES_FILE):
        print(f"  Indexing class notes...")
        with open(CLASS_NOTES_FILE, encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_by_sections(text, source="class_notes")
        print(f"    {len(chunks)} chunks")

        client.add(
            collection_name="class_notes",
            documents=[c["document"] for c in chunks],
            metadata=[{**c["metadata"], "raw_text": c["raw_text"]} for c in chunks],
        )
        print(f"    ✓ class_notes indexed")

    # 2. Company files
    for path in sorted(glob.glob(f"{COMPANIES_DIR}/*.md")):
        name = os.path.basename(path).replace(".md", "")
        col_name = name.replace("-", "_")
        print(f"  Indexing {name}...")

        with open(path, encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_markdown(text, source=name)
        print(f"    {len(chunks)} chunks")

        client.add(
            collection_name=col_name,
            documents=[c["document"] for c in chunks],
            metadata=[{**c["metadata"], "raw_text": c["raw_text"]} for c in chunks],
        )
        print(f"    ✓ {col_name} indexed")

    # 3. Exam case articles
    if os.path.isdir(ARTICLES_DIR):
        for path in sorted(glob.glob(f"{ARTICLES_DIR}/*.md")):
            name = os.path.basename(path).replace(".md", "")
            col_name = "article_" + name.replace("-", "_")
            print(f"  Indexing article: {name}...")

            with open(path, encoding="utf-8") as f:
                text = f.read()

            chunks = chunk_markdown(text, source=f"article:{name}")
            print(f"    {len(chunks)} chunks")

            client.add(
                collection_name=col_name,
                documents=[c["document"] for c in chunks],
                metadata=[{**c["metadata"], "raw_text": c["raw_text"]} for c in chunks],
            )
            print(f"    ✓ {col_name} indexed")

    print(f"\n  ✓ Index built at {VECTOR_DB_PATH}/")
    return True


# ── AI Context Curation ──────────────────────────────────

def curate_context(question, raw_results, company=None, api_keys=None):
    """
    Use a fast AI model to review vector search results and select
    only the most relevant chunks for this specific question.
    Returns reordered, filtered results.
    api_keys: dict with 'anthropic' and/or 'openai' keys from the request.
    """
    if not raw_results:
        return raw_results

    try:
        # Use whatever key is available — prefer Anthropic (the user's key)
        keys = api_keys or {}
        anthropic_key = keys.get("anthropic")
        openai_key = keys.get("openai") or os.environ.get("OPENAI_API_KEY")

        chunks_desc = "\n".join([
            f"CHUNK {i+1} [{r['source']}|{r['section']}]: {r['text'][:200]}..."
            for i, r in enumerate(raw_results)
        ])

        curation_msg = f"""You are a context curator for a Strategy MBA exam (Professor Luís Filipe Reis, PBS).

EXAM QUESTION: {question}
COMPANY: {company or 'Unknown'}

Below are {len(raw_results)} chunks retrieved by vector search. Select ONLY the chunks directly
relevant to answering this specific question. Order by importance.

Return ONLY a JSON array of chunk numbers (1-indexed):
{{"keep": [3, 1, 7, 5], "drop_reason": "brief explanation of what was irrelevant"}}

CHUNKS:
{chunks_desc}"""

        # Use Anthropic if available, fall back to OpenAI
        if anthropic_key:
            import anthropic
            c = anthropic.Anthropic(api_key=anthropic_key)
            resp = c.messages.create(
                model="claude-sonnet-4-6", max_tokens=300, temperature=0.1,
                messages=[{"role": "user", "content": curation_msg}],
            )
            text = resp.content[0].text.strip()
        elif openai_key:
            from openai import OpenAI
            c = OpenAI(api_key=openai_key)
            resp = c.chat.completions.create(
                model="gpt-5.4-mini", max_completion_tokens=300, temperature=0.1,
                messages=[{"role": "user", "content": curation_msg}],
            )
            text = resp.choices[0].message.content.strip()
        else:
            return raw_results  # No key available, skip curation
        # Parse JSON
        if "```" in text:
            for part in text.split("```")[1:]:
                cleaned = part.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                try:
                    result = json.loads(cleaned)
                    break
                except json.JSONDecodeError:
                    continue
        else:
            result = json.loads(text)

        keep_indices = result.get("keep", list(range(1, len(raw_results) + 1)))
        curated = [raw_results[i - 1] for i in keep_indices if 0 < i <= len(raw_results)]
        return curated if curated else raw_results

    except Exception:
        # If curation fails, return original results
        return raw_results


# ── Context retrieval ────────────────────────────────────

def get_context(question, company=None, max_chunks=20, api_keys=None):
    """
    Full RAG pipeline:
    1. Vector search across company + class_notes collections
    2. AI curator selects and reorders the most relevant chunks
    3. Returns formatted context string ready for LLM injection
    """
    client = _get_client()

    article_budget = 5 if company else 0
    company_budget = (max_chunks - article_budget) * 2 // 3 if company else 0
    notes_budget = max_chunks - company_budget - article_budget

    raw_results = []

    # Search article collection FIRST (exam case material)
    if company:
        art_col = "article_" + company.lower().replace("-", "_")
        try:
            hits = client.query(
                collection_name=art_col,
                query_text=question,
                limit=article_budget,
            )
            for hit in hits:
                raw_results.append({
                    "text": hit.metadata.get("raw_text", hit.document),
                    "source": f"article:{company}",
                    "section": hit.metadata.get("section", ""),
                    "score": hit.score,
                })
        except Exception:
            pass

    # Search company research collection
    if company:
        col_name = company.lower().replace("-", "_")
        try:
            hits = client.query(
                collection_name=col_name,
                query_text=question,
                limit=company_budget,
            )
            for hit in hits:
                raw_results.append({
                    "text": hit.metadata.get("raw_text", hit.document),
                    "source": f"company:{company}",
                    "section": hit.metadata.get("section", ""),
                    "score": hit.score,
                })
        except Exception:
            pass

    # Search class notes
    try:
        hits = client.query(
            collection_name="class_notes",
            query_text=question,
            limit=notes_budget,
        )
        for hit in hits:
            raw_results.append({
                "text": hit.metadata.get("raw_text", hit.document),
                "source": "class_notes",
                "section": hit.metadata.get("section", ""),
                "score": hit.score,
            })
    except Exception:
        pass

    if not raw_results:
        return ""

    # AI curation — select and reorder the most relevant chunks
    curated = curate_context(question, raw_results, company, api_keys=api_keys)

    # Format curated context — ARTICLE FIRST, then company data, then class notes
    article_context = [r for r in curated if r["source"].startswith("article:")]
    company_context = [r for r in curated if r["source"].startswith("company:")]
    notes_context = [r for r in curated if r["source"] == "class_notes"]

    parts = []
    if article_context:
        parts.append(f"## EXAM CASE ARTICLE — {company}")
        parts.append("(This is the article the professor gave. Reference it directly in your answer.)")
        for r in article_context:
            parts.append(r["text"])
            parts.append("")

    if company_context:
        parts.append(f"## SUPPLEMENTARY RESEARCH DATA — {company}")
        for r in company_context:
            parts.append(f"### {r['section']}")
            parts.append(r["text"])
            parts.append("")

    if notes_context:
        parts.append("## CLASS NOTES — Professor's Frameworks & Methodology")
        for r in notes_context:
            parts.append(f"### {r['section']}")
            parts.append(r["text"])
            parts.append("")

    context = "\n".join(parts)

    # Cap at ~32K chars (~8K tokens)
    if len(context) > 32000:
        context = context[:32000] + "\n\n[...truncated]"

    return context


def index_exists():
    """Check if the vector DB exists — filesystem only, no model loading."""
    if not os.path.exists(VECTOR_DB_PATH):
        return False
    collections = glob.glob(os.path.join(VECTOR_DB_PATH, "collection", "*"))
    return len(collections) >= 2


# ── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python context_engine.py build")
        print("  python context_engine.py query 'question' [company]")
        print("  python context_engine.py status")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "build":
        print("\n  Building vector index...\n")
        build_index()

    elif cmd == "query":
        question = sys.argv[2] if len(sys.argv) > 2 else "What is Porter+ analysis?"
        company = sys.argv[3].upper() if len(sys.argv) > 3 else None
        print(f"\n  Query: {question}")
        if company:
            print(f"  Company: {company}")
        print("  Retrieving + curating context...\n")
        context = get_context(question, company)
        print(f"  {len(context)} chars of curated context:\n")
        print(context[:5000])

    elif cmd == "status":
        if not index_exists():
            print("  Index not built. Run: python context_engine.py build")
        else:
            client = _get_client()
            for col in client.get_collections().collections:
                info = client.get_collection(col.name)
                print(f"  {col.name}: {info.points_count} vectors")
