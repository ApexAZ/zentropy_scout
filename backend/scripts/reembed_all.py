"""Re-embed all personas and job postings with the current embedding provider.

Standalone script (not an Alembic migration — external API calls don't belong
in migrations). Run after migration 024_gemini_embedding_dimensions.

REQ-028 §8.1 step 3: Re-embed via standalone script after vector column resize.

Usage:
    cd /path/to/zentropy_scout
    source backend/.venv/bin/activate
    python -m scripts.reembed_all [--dry-run]

Prerequisites:
    - Migration 024 applied (vector columns resized to 768)
    - GOOGLE_API_KEY set in .env (or whichever EMBEDDING_PROVIDER is configured)
    - Docker/PostgreSQL running
"""

import argparse
import asyncio
import logging

from sqlalchemy import select, text

from app.core.database import async_session_factory
from app.models.job_posting import JobEmbedding, JobPosting
from app.models.persona import Persona
from app.models.persona_settings import PersonaEmbedding
from app.providers.config import ProviderConfig
from app.providers.embedding.base import EmbeddingProvider
from app.providers.factory import get_embedding_provider
from app.services.job_embedding_generator import generate_job_embeddings
from app.services.persona_embedding_generator import (
    EmbedFunction,
    generate_persona_embeddings,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

_MODEL_VERSION = "1"
_MAX_SOURCE_HASH_LENGTH = 64


def _embed_fn(provider: EmbeddingProvider) -> EmbedFunction:
    """Create an embed function compatible with the generators.

    The generators expect: async def embed(text: str) -> list[list[float]]

    Args:
        provider: Embedding provider instance.

    Returns:
        Async callable wrapping provider.embed for single-text input.
    """

    async def embed(text_input: str) -> list[list[float]]:
        result = await provider.embed([text_input])
        return result.vectors

    return embed


async def reembed_personas(
    provider: EmbeddingProvider,
    dry_run: bool = False,
) -> int:
    """Re-embed all personas.

    Args:
        provider: Embedding provider to use.
        dry_run: If True, count but don't write.

    Returns:
        Number of personas processed.
    """
    embed = _embed_fn(provider)
    model_name = provider.config.embedding_model
    count = 0

    async with async_session_factory() as session:
        result = await session.execute(select(Persona))
        personas = result.scalars().all()
        logger.info("Found %d personas to re-embed", len(personas))

        for persona in personas:
            if dry_run:
                logger.info("  [dry-run] Would re-embed persona %s", persona.id)
                count += 1
                continue

            try:
                async with session.begin_nested():
                    await session.execute(
                        text("DELETE FROM persona_embeddings WHERE persona_id = :pid"),
                        {"pid": persona.id},
                    )

                    embeddings = await generate_persona_embeddings(
                        persona,
                        embed,
                        model_name=model_name,  # type: ignore[arg-type]
                    )

                    for emb_type, data in [
                        ("hard_skills", embeddings.hard_skills),
                        ("soft_skills", embeddings.soft_skills),
                        ("logistics", embeddings.logistics),
                    ]:
                        if data and data.vector:
                            session.add(
                                PersonaEmbedding(
                                    persona_id=persona.id,
                                    embedding_type=emb_type,
                                    vector=data.vector,
                                    model_name=model_name,
                                    model_version=_MODEL_VERSION,
                                    source_hash=data.source_text[
                                        :_MAX_SOURCE_HASH_LENGTH
                                    ]
                                    if data.source_text
                                    else "",
                                )
                            )

                await session.commit()
                count += 1
                logger.info(
                    "  Re-embedded persona %s (%d/%d)",
                    persona.id,
                    count,
                    len(personas),
                )
            except Exception:
                logger.exception(
                    "  Failed to re-embed persona %s, skipping", persona.id
                )
                await session.rollback()

    return count


async def reembed_jobs(
    provider: EmbeddingProvider,
    dry_run: bool = False,
) -> int:
    """Re-embed all job postings.

    Args:
        provider: Embedding provider to use.
        dry_run: If True, count but don't write.

    Returns:
        Number of job postings processed.
    """
    embed = _embed_fn(provider)
    model_name = provider.config.embedding_model
    count = 0

    async with async_session_factory() as session:
        result = await session.execute(select(JobPosting))
        jobs = result.scalars().all()
        logger.info("Found %d job postings to re-embed", len(jobs))

        for job in jobs:
            if dry_run:
                logger.info("  [dry-run] Would re-embed job %s", job.id)
                count += 1
                continue

            try:
                async with session.begin_nested():
                    await session.execute(
                        text("DELETE FROM job_embeddings WHERE job_posting_id = :jid"),
                        {"jid": job.id},
                    )

                    embeddings = await generate_job_embeddings(
                        job,
                        embed,
                        model_name=model_name,  # type: ignore[arg-type]
                    )

                    for emb_type, data in [
                        ("requirements", embeddings.requirements),
                        ("culture", embeddings.culture),
                    ]:
                        if data and data.vector:
                            session.add(
                                JobEmbedding(
                                    job_posting_id=job.id,
                                    embedding_type=emb_type,
                                    vector=data.vector,
                                    model_name=model_name,
                                    model_version=_MODEL_VERSION,
                                    source_hash=data.source_text[
                                        :_MAX_SOURCE_HASH_LENGTH
                                    ]
                                    if data.source_text
                                    else "",
                                )
                            )

                await session.commit()
                count += 1
                logger.info("  Re-embedded job %s (%d/%d)", job.id, count, len(jobs))
            except Exception:
                logger.exception("  Failed to re-embed job %s, skipping", job.id)
                await session.rollback()

    return count


async def main(dry_run: bool = False) -> None:
    """Run the re-embedding process.

    Args:
        dry_run: If True, count records without writing changes.
    """
    config = ProviderConfig.from_env()
    provider = get_embedding_provider(config)

    logger.info(
        "Re-embedding with provider=%s, model=%s, dimensions=%d",
        config.embedding_provider,
        config.embedding_model,
        config.embedding_dimensions,
    )

    if dry_run:
        logger.info("DRY RUN — no changes will be made")

    persona_count = await reembed_personas(provider, dry_run=dry_run)
    job_count = await reembed_jobs(provider, dry_run=dry_run)

    logger.info(
        "Done. Processed %d personas, %d job postings.",
        persona_count,
        job_count,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Re-embed all data with current provider"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count records without making changes",
    )
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
