"""Anime road-movie prompt direction that preserves the factual scene snapshot."""

from __future__ import annotations

from collections.abc import Sequence

from bunnyland.imagegen.prompt import (
    GeneratedPrompt,
    ImagePromptRequest,
    StructuredPromptEnhancer,
    VideoPromptRequest,
)

ANIME_DIRECTION = (
    "cinematic anime road movie, expressive but grounded character acting, warm hand-painted "
    "backgrounds; preserve every factual person, object, location, event, and action"
)


class StudioAnimeEnhancer(StructuredPromptEnhancer):
    name = "bunnyland.studio/anime-road-movie"

    async def enhance_image(
        self,
        request: ImagePromptRequest,
        *,
        examples: Sequence[GeneratedPrompt] = (),
    ) -> GeneratedPrompt:
        directed = request.model_copy(
            update={
                "extra": ", ".join(value for value in (request.extra, ANIME_DIRECTION) if value)
            }
        )
        return await super().enhance_image(directed, examples=examples)

    async def enhance_video(
        self,
        request: VideoPromptRequest,
        *,
        examples: Sequence[GeneratedPrompt] = (),
    ) -> GeneratedPrompt:
        directed = request.model_copy(
            update={
                "extra": ", ".join(value for value in (request.extra, ANIME_DIRECTION) if value)
            }
        )
        return await super().enhance_video(directed, examples=examples)


__all__ = ["ANIME_DIRECTION", "StudioAnimeEnhancer"]
