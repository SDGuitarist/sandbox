# Enrichment Design Principles

Findings on what makes personalized outreach feel like attention rather than surveillance. Derived from April 20, 2026 batch (30 sends, 7 replies, 3 warm leads).

---

## The Core Distinction: Attention vs Surveillance

Enrichment quality is not about finding verifiable data. It's about finding data that signals **you pay attention to their work** rather than **you looked them up**.

Both are technically "personalization." Recipients can tell the difference instantly.

**Attention:** "The Industry Pets episode on DJ Date Nite and her cat Monkey had a real softness to it." This requires having listened to the episode. It references a detail only someone who consumed the content would know.

**Surveillance:** "Saw that Caminito Punta Arenas close in Del Mar last spring." This requires a Zillow search. The recipient knows you didn't follow their career -- you queried a database.

---

## Hook Quality Hierarchy

Not all verifiable public hooks are equal. Ranked by how much "attention" they signal:

### Tier 1: Content They Created (highest signal)
- Specific episode details from their podcast/YouTube
- Quotes or ideas from articles they wrote
- Creative choices in their work (artistic direction, framing, theme)
- **Why it works:** Proves you consumed their output. Can't be faked with a search.
- **Example:** Siraji Thomas -- referenced specific episode guest + pet name. Reply: "Absolutely. And thanks for the kind words!"

### Tier 2: Opinions or Positions They Took
- Public statements, interviews, panel contributions
- Takes on industry topics
- **Why it works:** Shows you know what they think, not just what they did.
- **Example:** Sacha Boutros -- "Paris After Dark was a real statement of intent" frames her concert as a creative choice, not just an event.

### Tier 3: Events or Projects They Led
- Campaigns, shows, launches, community initiatives
- **Why it works:** References effort and vision, not just outcomes.
- **Example:** Madison Keith -- "Operation Max Wave was a solid one to watch unfold over four months" references sustained effort, not a single data point.

### Tier 4: Awards or Recognition They Received
- Lists, features, press mentions
- **Why it works partially:** Flattering but passive. They didn't create the recognition. Easy to find via search.
- **Example:** Shyla Day -- "100 Women to KNOW recognition" = no reply. Dwayne Crenshaw -- "Power 100 recognition" = no reply. Both well-researched, both ignored.

### Tier 5: Transactions or Metrics (lowest signal)
- Sales numbers, property closings, follower milestones
- **Why it fails:** Feels like data pull, not attention. "Saw your close" = "I checked Zillow."
- **Example:** All 9 real estate openers referenced closings. 0/9 warm leads.

---

## Three Durable Laws

### 1. Enrichment depth predicts response better than social proximity

| Evidence | Mutual Friends | Enrichment Source | Result |
|----------|:--------------:|:-----------------:|--------|
| Robert Kenyon | 371 mutual | Personal write (no Perplexity) | No reply |
| Tom Leech | 322 mutual | Personal write (no Perplexity) | No reply |
| Saman Hakimian | 272 mutual | Personal write (no Perplexity) | No reply |
| Siraji Thomas | -- | Perplexity (episode detail) | HOT |
| Madison Keith | -- | Perplexity (4-month campaign) | WARM |
| Sacha Boutros | -- | Perplexity (KPBS concert) | HOT |

Tier 1.5 (personal write, highest mutual) = 0% response. Tier 2-3 (Perplexity-researched) = 29% response. The enrichment layer is doing more work than the social graph.

### 2. Indirect CTA outperforms direct CTA

| CTA Type | Template | Response Rate |
|----------|----------|:------------:|
| Role-giving (indirect) | "I bet you know 2-3 people" | 33% (connectors) |
| Fear-disarming (indirect) | "Not for writing, but everything around it" | 20% (writers) |
| Problem-framing (direct) | "How fast do you respond to leads?" | 11% (real estate) |
| Peer-credibility (direct) | "I've been using AI to run my business" | 17% (small biz) |

Indirect CTAs give the recipient a role or disarm a fear. Direct CTAs frame a problem or assert credibility. Indirect wins.

### 3. Template-market fit is independent of personalization quality

The real estate openers were objectively well-researched. Verified Zillow data, specific addresses, accurate closing dates. The personalization quality was high. They still went 0/9 because the template itself ("How fast do you respond to leads?") triggered "vendor pitch" pattern matching that agents have seen hundreds of times.

**Implication for automation:** A system that generates great openers but pairs them with generic or poorly-fitted templates will underperform a system with mediocre openers and segment-tuned templates. Both levers matter. Template-market fit is the bigger one.

---

## Design Constraints for Lead-Scraper Enrichment

If automating the enrichment layer, these rules apply:

1. **Prioritize Tier 1-2 hooks over Tier 4-5.** Content created > awards received > transactions completed. If Perplexity can only find a property closing or a "top 100" list, flag it as low-quality and suggest skipping or writing a personal opener instead.

2. **"Verify before sending" is non-negotiable.** Every Perplexity-sourced hook must include a source URL. The sender clicks it before sending. This is the guard against hallucinated references.

3. **No-hook contacts should be held, not template-blasted.** The April 20 batch deliberately held back 32 contacts where Perplexity found nothing: "Sending template-only risks reading as broadcast." That discipline kept quality high.

4. **Segment determines template. Enrichment determines opener. Don't cross the streams.** A great opener can't save a template the recipient pattern-matches as a vendor pitch. A great template can't save a surveillance-style opener.
