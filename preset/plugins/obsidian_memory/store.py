"""Markdown fact storage for Obsidian Memory Provider."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Fact:
    """Structured fact with metadata."""
    id: str
    content: str
    category: str = "general"           # user_pref, project, tool, general
    entities: List[str] = field(default_factory=list)  # extracted entities
    tags: List[str] = field(default_factory=list)
    trust: float = 0.5                  # 0.0 - 1.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_session: str = ""
    source_turn: int = 0
    version: int = 1

    def to_frontmatter(self) -> Dict[str, Any]:
        """Convert to YAML frontmatter dict."""
        return {
            "id": self.id,
            "category": self.category,
            "entities": self.entities,
            "tags": self.tags,
            "trust": self.trust,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_session": self.source_session,
            "source_turn": self.source_turn,
            "version": self.version,
        }

    @classmethod
    def from_frontmatter(cls, fm: Dict[str, Any], content: str) -> "Fact":
        """Create Fact from frontmatter and content."""
        return cls(
            id=fm.get("id", str(uuid.uuid4())[:8]),
            content=content.strip(),
            category=fm.get("category", "general"),
            entities=fm.get("entities", []),
            tags=fm.get("tags", []),
            trust=float(fm.get("trust", 0.5)),
            created_at=fm.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=fm.get("updated_at", datetime.now(timezone.utc).isoformat()),
            source_session=fm.get("source_session", ""),
            source_turn=int(fm.get("source_turn", 0)),
            version=int(fm.get("version", 1)),
        )


class MarkdownFactStore:
    """Stores facts as individual Markdown files with YAML frontmatter."""

    CATEGORY_DIRS = ["user_pref", "project", "tool", "general"]

    def __init__(
        self,
        vault_path: str,
        default_trust: float = 0.5,
        min_trust: float = 0.3,
    ):
        self.vault_path = Path(vault_path).expanduser().resolve()
        self.facts_path = self.vault_path / "Brain" / "facts"
        self.default_trust = default_trust
        self.min_trust = min_trust
        self._lock = threading.RLock()
        self._init_vault()

    def _init_vault(self) -> None:
        """Create vault directory structure."""
        self.facts_path.mkdir(parents=True, exist_ok=True)
        for cat in self.CATEGORY_DIRS:
            (self.facts_path / cat).mkdir(exist_ok=True)

    def _fact_path(self, fact: Fact) -> Path:
        """Get file path for a fact."""
        safe_id = re.sub(r'[^\w\-]', '_', fact.id)
        return self.facts_path / fact.category / f"{safe_id}.md"

    def _write_fact_file(self, fact: Fact) -> None:
        """Write fact to markdown file with frontmatter."""
        path = self._fact_path(fact)
        fm = fact.to_frontmatter()
        # Write YAML frontmatter
        lines = ["---"]
        for k, v in fm.items():
            if isinstance(v, list):
                lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
            elif isinstance(v, str):
                lines.append(f'{k}: "{v}"')
            else:
                lines.append(f"{k}: {v}")
        lines.append("---")
        lines.append("")
        lines.append(fact.content)
        path.write_text("\n".join(lines), encoding="utf-8")

    def _read_fact_file(self, path: Path) -> Optional[Fact]:
        """Read fact from markdown file."""
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return None

        # Parse frontmatter
        if not text.startswith("---"):
            return None
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None

        import yaml
        try:
            fm = yaml.safe_load(parts[1]) or {}
        except Exception:
            return None

        content = parts[2].strip()
        return Fact.from_frontmatter(fm, content)

    def add_fact(
        self,
        content: str,
        *,
        category: str = "general",
        entities: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        trust: Optional[float] = None,
        session_id: str = "",
        turn_number: int = 0,
    ) -> Fact:
        """Add a new fact."""
        with self._lock:
            fact = Fact(
                id=str(uuid.uuid4())[:8],
                content=content.strip(),
                category=category if category in self.CATEGORY_DIRS else "general",
                entities=entities or [],
                tags=tags or [],
                trust=trust if trust is not None else self.default_trust,
                source_session=session_id,
                source_turn=turn_number,
            )
            self._write_fact_file(fact)
            logger.info("Added fact %s: %s", fact.id, content[:60])
            return fact

    def get_fact(self, fact_id: str) -> Optional[Fact]:
        """Get fact by ID."""
        with self._lock:
            for cat_dir in self.facts_path.iterdir():
                if not cat_dir.is_dir():
                    continue
                for f in cat_dir.glob(f"{fact_id}*.md"):
                    fact = self._read_fact_file(f)
                    if fact and fact.id == fact_id:
                        return fact
            return None

    def update_fact(
        self,
        fact_id: str,
        content: Optional[str] = None,
        trust_delta: float = 0.0,
        category: Optional[str] = None,
    ) -> Optional[Fact]:
        """Update existing fact."""
        with self._lock:
            fact = self.get_fact(fact_id)
            if not fact:
                return None

            old_path = self._fact_path(fact)
            if content is not None:
                fact.content = content.strip()
            if trust_delta != 0.0:
                fact.trust = max(0.0, min(1.0, fact.trust + trust_delta))
            if category and category in self.CATEGORY_DIRS:
                fact.category = category

            fact.updated_at = datetime.now(timezone.utc).isoformat()
            fact.version += 1

            # Remove old file if category changed
            if old_path.exists():
                old_path.unlink(missing_ok=True)

            self._write_fact_file(fact)
            logger.info("Updated fact %s (v%d)", fact.id, fact.version)
            return fact

    def delete_fact(self, fact_id: str) -> bool:
        """Delete a fact."""
        with self._lock:
            fact = self.get_fact(fact_id)
            if not fact:
                return False
            self._fact_path(fact).unlink(missing_ok=True)
            logger.info("Deleted fact %s", fact_id)
            return True

    def search_facts(
        self,
        query: str,
        *,
        category: Optional[str] = None,
        min_trust: Optional[float] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search facts by keyword (ripgrep-style via filesystem)."""
        with self._lock:
            min_t = min_trust if min_trust is not None else self.min_trust
            query_lower = query.lower()
            query_words = set(re.findall(r'\w+', query_lower))

            results = []
            cats = [category] if category else self.CATEGORY_DIRS

            for cat in cats:
                cat_dir = self.facts_path / cat
                if not cat_dir.exists():
                    continue
                for f in cat_dir.glob("*.md"):
                    fact = self._read_fact_file(f)
                    if not fact or fact.trust < min_t:
                        continue

                    # Simple keyword scoring
                    content_lower = fact.content.lower()
                    content_words = set(re.findall(r'\w+', content_lower))
                    tag_words = set()
                    for tag in fact.tags:
                        tag_words.update(re.findall(r'\w+', tag.lower()))

                    all_words = content_words | tag_words
                    if not query_words:
                        continue

                    overlap = len(query_words & all_words)
                    if overlap == 0:
                        continue

                    # Jaccard-like score
                    score = overlap / max(len(query_words), 1)
                    # Boost for entity matches
                    for ent in fact.entities:
                        if ent.lower() in query_lower:
                            score += 0.2

                    results.append({
                        "id": fact.id,
                        "content": fact.content,
                        "category": fact.category,
                        "entities": fact.entities,
                        "tags": fact.tags,
                        "trust": fact.trust,
                        "score": score,
                        "created_at": fact.created_at,
                    })

            # Sort by score desc, then trust desc
            results.sort(key=lambda x: (x["score"], x["trust"]), reverse=True)
            return results[:limit]

    def probe_entity(self, entity: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find all facts mentioning an entity."""
        with self._lock:
            entity_lower = entity.lower()
            results = []
            for cat_dir in self.facts_path.iterdir():
                if not cat_dir.is_dir():
                    continue
                for f in cat_dir.glob("*.md"):
                    fact = self._read_fact_file(f)
                    if not fact:
                        continue
                    # Check entities list
                    if any(entity_lower in e.lower() for e in fact.entities):
                        results.append({
                            "id": fact.id,
                            "content": fact.content,
                            "category": fact.category,
                            "trust": fact.trust,
                        })
                    # Also check content
                    elif entity_lower in fact.content.lower():
                        results.append({
                            "id": fact.id,
                            "content": fact.content,
                            "category": fact.category,
                            "trust": fact.trust,
                        })

            results.sort(key=lambda x: x["trust"], reverse=True)
            return results[:limit]

    def list_facts(self, category: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent facts."""
        with self._lock:
            results = []
            cats = [category] if category else self.CATEGORY_DIRS
            for cat in cats:
                cat_dir = self.facts_path / cat
                if not cat_dir.exists():
                    continue
                for f in sorted(cat_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
                    fact = self._read_fact_file(f)
                    if fact:
                        results.append({
                            "id": fact.id,
                            "content": fact.content[:200],
                            "category": fact.category,
                            "trust": fact.trust,
                            "created_at": fact.created_at,
                        })
                    if len(results) >= limit:
                        break
            return results[:limit]

    def count_facts(self) -> int:
        """Total fact count."""
        with self._lock:
            count = 0
            for cat_dir in self.facts_path.iterdir():
                if cat_dir.is_dir():
                    count += len(list(cat_dir.glob("*.md")))
            return count

    def get_all_facts(self) -> List[Fact]:
        """Get all facts (for embedding indexing)."""
        with self._lock:
            facts = []
            for cat_dir in self.facts_path.iterdir():
                if not cat_dir.is_dir():
                    continue
                for f in cat_dir.glob("*.md"):
                    fact = self._read_fact_file(f)
                    if fact:
                        facts.append(fact)
            return facts

    def fact_exists_similar(self, content: str, threshold: float = 0.92) -> Optional[Fact]:
        """Check if very similar fact exists (simple content overlap)."""
        with self._lock:
            new_words = set(re.findall(r'\w+', content.lower()))
            if not new_words:
                return None

            best_match = None
            best_score = 0.0
            for cat_dir in self.facts_path.iterdir():
                if not cat_dir.is_dir():
                    continue
                for f in cat_dir.glob("*.md"):
                    fact = self._read_fact_file(f)
                    if not fact:
                        continue
                    existing_words = set(re.findall(r'\w+', fact.content.lower()))
                    if not existing_words:
                        continue
                    overlap = len(new_words & existing_words)
                    union = len(new_words | existing_words)
                    if union == 0:
                        continue
                    score = overlap / union  # Jaccard
                    if score > best_score:
                        best_score = score
                        best_match = fact

            if best_match and best_score >= threshold:
                return best_match
            return None