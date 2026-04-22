---
title: Template Engine
parent: Architecture
grand_parent: Technical Reference
nav_order: 6
docs_version: "2.3.1"
---

# Template Engine

The template engine resolves `{variable}` placeholders in EPG titles, descriptions, and filler content. It supports 205 variables across 17 categories, 20 condition evaluators, and suffix rules for multi-game context.

## Architecture

```
TemplateResolver
  ├── VariableRegistry (205 variables, 17 categories)
  ├── ConditionEvaluator (20 evaluators)
  └── ContextBuilder (Event + Team → TemplateContext)
```

## Variable Resolution Pipeline

1. Parse `{variable}` and `{variable.suffix}` patterns from template string
2. Look up each variable in the `VariableRegistry`
3. Check the variable's `SuffixRules` to determine which game contexts are valid
4. Call the variable's extractor function with the appropriate `GameContext`
5. Replace placeholders with resolved values
6. Clean up artifacts (empty parentheses, double spaces, trailing punctuation)

## Suffix Rules

Each variable declares which game contexts it supports:

| Suffix | Context | Example |
|--------|---------|---------|
| `{var}` (base) | Current/next game | `{game_date}` → `"Mar 15"` |
| `{var.next}` | Next scheduled game | `{game_date.next}` → `"Mar 18"` |
| `{var.last}` | Last completed game | `{game_date.last}` → `"Mar 12"` |

| Rule | Base | .next | .last | Used By |
|------|------|-------|-------|---------|
| `ALL` | Yes | Yes | Yes | Most variables (opponent, game_date, scores) |
| `BASE_ONLY` | Yes | No | No | Team constants (team_name, league, sport) |
| `BASE_NEXT_ONLY` | Yes | Yes | No | Odds (no odds for past games) |

## Variable Categories

| Category | Count | Key Variables |
|----------|-------|---------------|
| **Identity** | 20 | team_name, opponent, league, sport, team_short, matchup_short |
| **Combat** | 26 | fighter1, fighter2, card_segment, round_number, fight_result_method |
| **Conference** | 20 | college_conference, pro_division, division_abbrev |
| **Records** | 18 | team_record, opponent_record, team_wins, team_losses |
| **Streaks** | 18 | win_streak, loss_streak, streak_detail, streak_emoji |
| **Home/Away** | 17 | is_home, vs_at, home_team_name, away_team_short |
| **Scores** | 15 | team_score, opponent_score, final_score, score_differential |
| **DateTime** | 10 | game_date, game_time, days_until, hours_until |
| **Rankings** | 9 | team_rank, opponent_rank, is_ranked, rank_text |
| **Odds** | 7 | odds_spread, odds_over_under, odds_moneyline_team |
| **Soccer** | 6 | soccer_match_league, soccer_group_name, soccer_match_matchday |
| **Statistics** | 6 | team_ppg, opponent_ppg, team_wpct |
| **Outcome** | 5 | result, result_text, result_emoji, final_status |
| **Broadcast** | 4 | broadcast_simple, network, market |
| **Venue** | 4 | venue_full, venue_name, venue_city |
| **Standings** | 4 | playoff_seed, games_back |
| **Playoffs** | 4 | is_playoff, is_preseason, season_type |

Variables are registered via decorator in `teamarr/templates/variables/` (one file per category).

## Condition Evaluators

20 evaluators for conditional descriptions. Lower priority number = evaluated first. Priority 100 is the default (always matches).

| Condition | Description | Value Param |
|-----------|-------------|-------------|
| `always` | Legacy: always true | No |
| `is_home` | Team playing at home | No |
| `is_away` | Team playing away | No |
| `win_streak` | On N+ game win streak | Min streak length |
| `loss_streak` | On N+ game loss streak | Min streak length |
| `is_ranked` | Team ranked top 25 | No |
| `is_ranked_opponent` | Opponent ranked top 25 | No |
| `is_ranked_matchup` | Both teams top 25 | No |
| `is_top_ten_matchup` | Both teams top 10 | No |
| `is_conference_game` | Same conference (college) | No |
| `is_playoff` | Playoff game | No |
| `is_preseason` | Preseason game | No |
| `is_national_broadcast` | National TV (ABC, ESPN, NBC, etc.) | No |
| `has_odds` | Betting odds available | No |
| `opponent_name_contains` | Opponent name includes string | Search string |
| `is_knockout` | KO/TKO finish (MMA) | No |
| `is_submission` | Submission finish (MMA) | No |
| `is_decision` | Decision (MMA) | No |
| `is_finish` | Any finish (KO/TKO/sub) | No |
| `went_distance` | Went all rounds (MMA) | No |

### Conditional Description Selection

Templates can define multiple descriptions with conditions and priorities:

```json
[
  {"condition": "win_streak", "condition_value": "5", "priority": 10,
   "template": "{team_name} riding a {win_streak}-game win streak!"},
  {"condition": "is_playoff", "priority": 20,
   "template": "Playoff {sport}: {team_name} vs {opponent}"},
  {"priority": 100,
   "template": "{team_name} vs {opponent}"}
]
```

The selector evaluates conditions by priority (lowest first). If multiple match at the same priority, one is chosen randomly. The selected template is then passed through variable resolution.

## Template Context

The context builder assembles a `TemplateContext` from events and team data:

| Component | Contents | Variables |
|-----------|----------|-----------|
| `TeamChannelContext` | Team identity (name, league, sport, logo) | `BASE_ONLY` vars |
| `GameContext` (current) | Current/next event, home/away, opponent, odds | `ALL` + `BASE_NEXT_ONLY` vars |
| `GameContext` (.next) | Next scheduled game | `.next` suffix vars |
| `GameContext` (.last) | Last completed game | `.last` suffix vars |
| `TeamStats` | Season record, standings, streak | `ALL` vars |

## Three Parallel Resolution Paths

Template resolution happens in three places that **must stay in sync**:

| Path | Purpose | File |
|------|---------|------|
| Channel creation | New channel name, tvg_id, logo | `lifecycle/service.py` |
| Channel sync | Update existing channel | `lifecycle/service.py` |
| EPG generation | XMLTV programme content | `consumers/event_epg.py` |

When adding new template variables, all three paths must be updated.

## File Locations

| File | Purpose |
|------|---------|
| `templates/resolver.py` | Variable resolution pipeline |
| `templates/conditions.py` | 20 condition evaluators |
| `templates/context.py` | Context dataclasses (Odds, GameContext, TemplateContext) |
| `templates/context_builder.py` | Build TemplateContext from Event + Team |
| `templates/variables/` | 17 category modules with 197 variable definitions |
| `templates/variables/registry.py` | VariableRegistry singleton |
| `templates/sample_data.py` | Test fixtures for UI preview |
