"""Summary variables: provider editorial/context copy for a game.

Raw 1:1 maps of provider fields — no post-processing. Each is empty when the
provider didn't supply it (sparse by nature; see
docs/reference/architecture/gracenote-template-design.md). All three free-tier
vars come from the scoreboard payload Teamarr already fetches, so they cost no
extra API calls.
"""

from teamarr.templates.context import GameContext, TemplateContext
from teamarr.templates.variables.registry import (
    Category,
    SuffixRules,
    register_variable,
)


@register_variable(
    name="game_recap",
    category=Category.SUMMARY,
    suffix_rules=SuffixRules.ALL,
    description="Postgame recap blurb from the provider (e.g. 'Jalen Brunson and the "
    "Comeback Knicks did it again.'). Empty until a game is final. Free/bulk.",
)
def extract_game_recap(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    if not game_ctx or not game_ctx.event:
        return ""
    return game_ctx.event.game_recap or ""


@register_variable(
    name="game_event_note",
    category=Category.SUMMARY,
    suffix_rules=SuffixRules.ALL,
    description="Marquee/playoff designation for the game (e.g. 'NBA Finals - Game 5', "
    "'Stanley Cup Final - Game 6', 'WNBA Commissioner's Cup'). Empty for ordinary "
    "regular-season games. Free/bulk.",
)
def extract_game_event_note(ctx: TemplateContext, game_ctx: GameContext | None) -> str:
    if not game_ctx or not game_ctx.event:
        return ""
    return game_ctx.event.game_event_note or ""
