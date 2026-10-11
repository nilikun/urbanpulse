# UrbanPulse: Urban Resilience Index concept brief

> The proposal UrbanPulse implements. Cited companies and loans are public examples of market practice; no affiliation is implied. Where the build has tested or changed a point, a note in *italics* says so and links to the evidence.

## Summary

Singapore's towns are getting hotter, yet the residents most at risk get the least protection. Planners can model wind and temperature but not who a plan cools. Developers treat mandatory greenery as a cost whose benefits they cannot prove after completion. We resolve this with three parts:

* an index that scores every block on who it cools;
* a community credit system that verifies real outcomes, such as rooftop-farm harvests;
* a project pass that turns required greenery into measurable returns for developers and evidence-based targets for planners.

| Who | Pain point observed | What we resolve |
|---|---|---|
| Vulnerable residents | Most exposed, least protected: about half of 400+ HDB flats studied were hotter inside than outdoors | Plans scored on who they cool, with an inclusion check for seniors and rental households |
| Planners | Tools model wind, sun and temperature, not people; evidence is scattered and at planning-area level | One map, block-level scores, benchmarks from towns that worked |
| Developers | Greenery is mandatory (30–40% of site area; Green Mark Platinum Super Low Energy on government-sold land) but seen as a cost | A project pass that turns required greenery into returns: sale premium, sustainability-linked loans, subsidies, rent |
| Developers and lenders | Green claims can't be verified after completion | Verified post-occupancy data from community credits, e.g. kg harvested on rooftop farms |
| Everyone | Rules count leaves, not beneficiaries; the Green Plan sets no heat target | An index measuring cooling, access and use by people, kept current by residents' reports |

1. **The index:** open data on one map scores every block 0–100 on six pillars: heat, shade, green-blue space, community and green use, access, and flooding. Planners and developers upload their own plan and get a score, an inclusion check and nature-based tweaks showing the gain each would bring.
2. **Community data:** residents and Active Ageing Centres (AACs) earn credits for verified actions and reports. These are led by rooftop farms (kg harvested) and community gardens, plus shade, upkeep and comfort. The reports validate the model and re-learn its weights, so each town improves the next.
3. **How people pay and benefit:** developers, starting with Government Land Sales (GLS) sites, buy a project pass. It turns mandatory greenery into returns (sales premium, sustainability-linked financing, subsidies, rent), backed by verified post-occupancy data for ESG reporting. Planners buy seats or a licence. Part of the revenue funds the block pots behind residents' credits.

**Overall flow (data, tools and payment).** Open data and resident reports feed the platform. Planners and developers pay for its scores and tweaks, and that revenue flows back to the residents who keep the data current.

## Purpose

An interactive website to help planners and developers design new towns that are cooler, greener, more flood-resilient and inclusive. It is powered by an index that scores how liveable and resilient each HDB town is, learning from the best performers to set design targets. Planners and developers upload their own scenario. The index scores it, and the model suggests specific tweaks, each showing the score it would gain, before anything is built.

## Problem

Planners can test how a new town's layout affects wind, sun and temperature, but not who it cools. Singapore is getting hotter, and seniors, low-income households and rental-flat tenants are the least protected. In a study of 400+ HDB flats, about half were hotter inside than outdoors.

Publicly available evidence on heat, greenery, flooding and vulnerability sits in separate datasets and studies, often at planning-area level. So it is hard to see which past design choices worked for residents, or which vulnerable groups a new plan might leave out. Residents, who could help cool their neighbourhoods, have no role or incentive.

## Gaps

Existing tools model the physical environment well. What is missing is the people and equity layer, and a link between past design choices and outcomes.

| Gap | Evidence |
|---|---|
| Design tools model physics, not people | HDB/A*STAR [Integrated Environmental Modeller](https://www.ura.gov.sg/land-planning/master-plan/master-plan-2025/themes/strengthening-urban-resilience/a-cool-city-in-a-warming-world/) (used for Tengah) simulates wind, sun and temperature; URA's cooling page does not mention elderly or vulnerable residents |
| Greenery rules count leaves, not who benefits | [URA greenery rules](https://www.ura.gov.sg/Corporate/Guidelines/Development-Control/Residential/Flats-Condominiums/Greenery): Green Plot Ratio 3–4, tiered by plot ratio and location, not heat or vulnerability |
| Liveability and heat are measured separately | [Benita 2021](https://ideas.repec.org/a/sae/envirb/v48y2021i7p2006-2022.html) liveability index (203 subzones) has no heat; heat vulnerability maps focus on exposure and population |
| Heat risk mapped too coarsely | Singapore-ETH 2020 vulnerability map is by planning area ([Mothership](https://mothership.sg/2024/02/spore-hotter-sengkang-hot-wp-motion//amp)) |
| Town-level link between design and outcome not found | City-level heat tracked 1990–2024 ([npj Urban Sustainability 2025](https://www.nature.com/articles/s42949-025-00315-8)); no town-by-town study linked to design choices found yet |
| Indoor heat unmapped | ~Half of 400+ flats hotter inside than outdoors ([Her World, May 2026](https://www.herworld.com/life/your-home-hotter-outside-what-singapores-latest-housing-study-reveals)); >90% of rental flats lack air-con ([NUS, WSBE 2026, preliminary](https://wsbe-2026.p.asnevents.com.au/days/2026-06-11/abstract/130130)) |
| No heat target | [Green Plan 2030](https://www.greenplan.gov.sg/targets/) targets parks within a 10-minute walk, trees and buildings, but sets no heat target |
| Averages hide inequity | Green-space cooling is inequitably distributed; lower-income groups drive the gap ([Xu et al. 2025](https://ideas.repec.org/a/eee/ecoser/v73y2025ics2212041625000312.html)) |

## Solution

The website turns scattered data into design targets and suggestions, and gets smarter with every town Singapore builds.

1. **Integrate:** one live map of heat and felt heat, satellite heat history, greenery, flooding, buildings, mobility, seniors and access, from open data.
2. **Learn and benchmark:** score existing HDB towns down to block level, track how their heat changed, and turn the best performers into design targets.
3. **Score the scenario:** the planner or developer draws or uploads a scenario (layout, parks, flat mix, routes). The index scores it on all six pillars and runs the inclusion check.
4. **Suggest tweaks:** the model proposes specific nature-based changes with their score gain (e.g. "green pocket at site X: +6 access, 42 more rental households reached"). The user accepts or rejects each and compares versions side by side. The user stays in control; whole generated alternatives come later, once community data has validated the model.
5. **Check inclusion:** a plan cannot score well on average if its worst-served 20% of blocks, or its senior flats, fall far behind.
6. **Keep it alive with the community:** after move-in, residents and AAC seniors earn credits for verified shade, green pockets and neighbour check-ins. Actions and indoor readings feed back into step 2.
7. **Show the value:** a separate value lens shows potential resale uplift from cooling and greening. It sits outside the score, so seniors' homes are never marked down.

*Build notes: steps 1, 2, 4, 5 and 7 are implemented island-wide ([`uri/`](../uri)). Step 3 is implemented as fixed-reference scoring, so any scenario is scored on today's national distribution. Step 5 changes the recommended package in Woodlands ([Figure 3](../figures/fig3_tweaks.png)). Step 7 found no resale premium for block-level canopy within town and month ([Figure 4](../figures/fig4_value_robustness.png)).*

## Part 1: The index

Six pillars score each block 0–100 (higher = more resilient). Vulnerability weights the result rather than adding to it. Weights start at the defaults below, shift with the user's view, and are re-learned from community data.

| Pillar | Default weight (%) | What it measures | How it adjusts |
|---|---|---|---|
| Heat exposure | 25 | Surface temperature near the block; hours at high WBGT; felt-heat gap | Live NEA readings every 5–15 min; Landsat history yearly |
| Shade and cooling | 20 | % of walking routes shaded; canopy within 200 m; covered linkways | Rises as shade and trees are added; weight up in senior view |
| Green-blue space | 15 | Park area within 10 minutes; distance to park connector and water | Changes with new parks in a plan; weight re-learned from use and comfort data |
| Community and green use | 15 | Garden use, social connection, upkeep, restorative quality, species seen | Monthly from community reports; low confidence until enough reports; actions decay unless re-verified |
| Access and mobility | 15 | Shaded walking distance to AAC, clinic, hawker centre, MRT, bus stop | Changes with new amenities or routes; walking threshold adjustable (default 400 m) |
| Flood resilience | 10 | Distance to PUB flood-prone location; flood alerts | Updates when PUB revises its list; weight up in planner view |

Block score = Σ (pillar weight × pillar score). Town score = average of block scores, weighted by need. Each indicator carries a confidence flag, and every plan also reports its inclusion gap.

*Build note: WBGT failed the "block-level data" test (27 stations; ρ = −0.05 with block surface heat) and is kept as a context layer. The heat pillar uses 30 m satellite surface heat.*

### How the pillars fit together

Vulnerability should weight the other pillars, not be added to them: added as a pillar, a block scores higher simply by housing fewer seniors.

1. **Indicators → pillars:** each indicator becomes a 0–100 percentile score; a pillar is the average of its indicators.
2. **Five environment pillars → block resilience score:** a weighted sum of heat exposure, shade and cooling, green-blue space, flood resilience, and access and mobility. Shade feeds access only through heat-adjusted routes, so it is not counted twice.
3. **Inclusion check:** report the gap between the worst-served 20% of blocks and the median. A plan with a large gap is flagged even if its average is high.

Outputs per plan: town resilience score (need-weighted), inclusion gap, and the pillar breakdown showing what to fix.

### Why these inputs

An input is in only if it passes all five tests; anything that fails is left out or parked in phase 2.

1. **Evidence:** a Singapore or peer-reviewed study links it to heat exposure or heat harm.
2. **Plannable:** a planner can change it in a new-town plan, or needs it to target who benefits.
3. **Data:** free, open, current and at block or precinct level.
4. **Not redundant:** not already captured by another indicator (drop one of any pair correlating above 0.8).
5. **Predictive:** it improves how well the index predicts surface heat, WBGT readings or resale value in validation.

| Pillar | Why it is in |
|---|---|
| Heat exposure | The outcome itself; Landsat and NEA give open, current data |
| Vulnerability | Heat harm concentrates in seniors and low-income households (Singapore-ETH 2020; Xu et al. 2025) |
| Shade and cooling | Street shade cut extreme heat stress occurrences by 92% in one-north (CARES study) |
| Green-blue space | Green Plan's 10-minute park target; park cooling reach is measurable |
| Flood resilience | Completes the blue-green brief; PUB publishes current flood-prone locations |
| Access and mobility | Seniors walk to daily needs; HDB blocks average 294 m to amenities (Lee et al.) |

Left out, and why: energy (only 2009–2013 data found), solar (no open block data), waste (not checked), block-level biodiversity (no data). Block age stays only as a low-confidence proxy, to drop if it fails test 5.

### Data sources

Every input is free: data.gov.sg under the Singapore Open Data Licence (credit required), plus free-account satellite data and OpenStreetMap.

| Layer | Main sources |
|---|---|
| Heat | NEA real-time weather, NEA WBGT, Landsat surface temperature 1982–now |
| People | SingStat population by subzone, HDB Property Information |
| Green | URA Master Plan land use, Park Connector Loop, Sentinel-2 |
| Flooding | PUB flood-prone areas (Nov 2025) |
| Built form and shade | OpenStreetMap, NUS HDB 3D model, LTA covered linkways (check currency) |
| Mobility and access | MRT exits, cycling paths, LTA DataMall bus stops, eldercare, hawker centres |
| Value | HDB resale prices |

Phase 2, no open data yet: indoor temperature (collect), heat illness (MOH HEATMAP, ~2028), energy, solar, block-level biodiversity.

## Part 2: Community data

### Community credits

Residents earn credits for verified actions that cool their block, and for reports that tell the model how green spaces are actually used. Credits are worth more where need is higher.

| Action | Indicator it feeds | Verified by | Output measure (unit) |
|---|---|---|---|
| Shade added along a route (sail, trellis, planter) | % of route shaded: recalculate that segment | Photo + town council | Shaded metres added; route shade % (change in points) |
| Tree planted | Canopy within 200 m: crown area by species, once established | NParks or town council | Crown area added (m²); canopy % within 200 m |
| Green pocket created or maintained | Seniors within 200 m of a cool refuge | Photo + town council | Seniors newly within 200 m of a refuge (count) |
| Neighbour check-in on hot days | % of at-risk seniors visited in the last 30 days on high-WBGT days | AAC | % of at-risk seniors visited per 30 days |
| Indoor temperature reading | Indoor heat (measured, not modelled) | AAC or volunteer | Indoor °C per block (mean and peak); readings per month |
| Join or host a community garden session; bring a new neighbour | Social connection: attendance, new ties | QR at site + AAC | Attendees per session by age; first-time attendees per month |
| Quarterly 2-minute survey (3-item loneliness scale) | Social connection: loneliness trend | Anonymous, once per quarter | Average loneliness score per block (3–9, lower is better), per quarter |
| Report a garden problem; adopt a garden bed; take a watering or weeding shift | Condition and upkeep: issues, condition rating, time to fix | Geotagged photo + town council | Open issues per site; days to fix; stewardship hours per month |
| Rate a garden or green space after a visit (short restorativeness scale) | Restorative quality per space | QR at site | Average rating per site, by time of day; ratings per site |
| Plant native and pollinator species; log butterfly and bird sightings | Biodiversity at the garden: species seen per month | Photo + garden lead | Species seen per site per month |

**From output to score:** each output is turned into a 0–100 percentile across all blocks or sites (flipped where lower is better), then averaged into its pillar. Sites with too few reports that month are marked low confidence, not scored.

**How much:** credits = change in the indicator × the block's need weight (more seniors and rental households, more credits). Report-only actions earn a fixed amount; under-sampled spaces earn a bounty.

**Rules**

* Verify before paying; only the first valid report of a problem counts.
* Pay for taking part, never for the answer.
* Weekly cap per person, so a few users don't dominate the data.
* Physical actions decay unless re-verified; the period is an adjustable setting per action type (no Singapore source found).
* Map labels separate measured, claimed and human-reported data; scores recalculate monthly.
* Seniors can log through AAC staff on paper; no smartphone needed.
* Privacy: consent, aggregates by block or site only, in line with the PDPA.

**Spending credits:** personal vouchers, or points in an existing health app (needs a partnership); recognition through garden steward badges shown on site.

**What paid subscribers gain from credits**

* **Developers:** credited reports give verified post-occupancy data (farm harvest, microforest survival, use and comfort) to prove sustainability-linked loan targets, back marketing claims and support ESG reporting.
* **Planners:** reports show which green spaces residents actually use and maintain, so new-town targets rest on observed evidence rather than assumptions.
* **Both:** a steady flow of fresh, block-level data that open sources cannot provide, which keeps scores, tweaks and benchmarks current.

### Hero feature: rooftop farm

The rooftop farm is our lead community feature because its output (kg harvested) is easy to verify and links to several returns. HDB carpark rooftops have already been tendered to urban farms ([2020 round: 9 sites, 1,808–3,311 m², 3-year terms](https://agfundernews.com/singapore-food-and-housing-agencies-to-rent-out-public-rooftops-for-urban-farms)), and urban farming is a target in [CDL's S$300M sustainability-linked loan with DBS](https://www.cdl.com.sg/newsroom/cdl-and-dbs-launch-s-300-million-multi-currency-sustainability-linked-loan-to-advance-nature-based-urban-development-solutions-in-singapore) (May 2026).

| Metric | Community source | Return it proves |
|---|---|---|
| Harvest (kg per month, by crop) | Logs weighed at collection | Loan target met; produce or rent income |
| Volunteer hours, residents involved | QR check-ins at farm sessions | Social connection; ESG reporting |
| Produce shared with seniors (kg, households) | AAC confirms receipt | Inclusion; ESG reporting |
| Roof surface temperature, farmed vs bare | Volunteer spot readings plus satellite | Cooling for top-floor flats (hypothesis to test) |
| Crop failures, pests, time to fix | Upkeep reports | Lower maintenance cost |

To decide: who runs the farm (commercial operator, community, or hybrid), who weighs the harvest, and whether farm area counts toward URA's greenery requirement (LUSH 3.0 reportedly supports rooftop farming; terms to verify).

### How community data improves the model

The open-data model makes predictions; community reports check whether they hold. For example, two parks with the same score may draw 40 vs 5 seniors an hour because only one has shaded seats and good upkeep.

1. **Validate:** test whether high scores match real use and comfort.
2. **Learn weights:** set each indicator's weight by how well it predicts use and comfort, instead of guessing or weighting equally.
3. **Set targets:** design features linked to high use (e.g. shaded seats every 100 m) become benchmarks for new towns.
4. **Ground the simulator:** replace assumptions (e.g. seniors use a cool spot within 200 m) with Singapore observations.

The loop: model predicts → residents report → compare → adjust indicators and weights → better predictions for the next town. Credits keep the reports coming.

**The whole flow (7 steps, 1 loop).** Open data builds the index; benchmarks and simulation shape a new town; residents' verified reports then validate the model and re-learn its weights, so each town improves the next. Subscriptions fund the credits that keep reports coming.

## Part 3: How people pay and benefit

Developers are the main paying customers; planners are a smaller segment.

### Why it matters to subscribers

Community data is what open data cannot give, so it is the main reason planners and developers would pay.

1. **Evidence, not claims:** "lush landscaping" becomes "shaded seating every 100 m doubles senior use." This informs which amenities are worth the land, backs marketing claims, and supports ESG reporting on social and nature outcomes.
2. **Post-occupancy performance:** developers rarely learn whether their green spaces work after move-in; credit reports build a benchmark library of designs that actually get used and maintained.
3. **Credibility:** a score validated against real use is worth paying for; one built on assumptions is not.
4. **Real change, measured:** credited actions physically improve the neighbourhood (more shade and canopy, microforests, rooftop farms, regular check-ins on seniors), and each is verified, so subscribers can report actual environmental and social gains in their ESG disclosures, not just plans.

### For developers

* **Single plot:** score the design against its 400 m neighbourhood, check URA greenery compliance, and get tweaks that place public green space where nearby residents need it most.
* **Joint development:** score several sites together, plan shared green links and amenities across them, and compare combined vs separate scores; cost and credit splits stay adjustable for any mix of partners.
* **Community data's role:** shows what works around the site, backs each tweak with observed evidence, and gives post-occupancy proof for ESG reporting.

### Making mandatory greenery pay

Greenery provision is a mandatory development cost. The project pass converts this obligation into measurable returns, through sales premiums, sustainability-linked financing, subsidies and rental income, while improving neighbourhood resilience. Our initial target segment is developers of Government Land Sales sites, who are subject to the most stringent sustainability standards.

**What is already required**

| Requirement | Applies to | Demands | Confidence |
|---|---|---|---|
| [URA landscape replacement + Green Plot Ratio](https://www.ura.gov.sg/Corporate/Guidelines/Development-Control/Residential/Flats-Condominiums/Greenery) | Private developments | Greenery of 30–40% of site area (70–100% in strategic areas); Green Plot Ratio 3–4; publicly accessible | Checked |
| BCA Green Mark (mandatory) | New buildings of 2,000 m²+ floor area | At least Green Mark certification | Search summary only |
| Higher standard on government-sold land | Sites sold on or after 30 June 2022 | Green Mark Platinum Super Low Energy (≥60% energy improvement over 2005 codes) | Search summary only |

**How required greenery can earn**

| Return | Evidence | How the tool helps |
|---|---|---|
| Higher sale price | Condos within 1 km of Jurong Lake Gardens averaged $1,617 psf vs $1,383 psf within 2 km; simple averages, not proof of cause ([EdgeProp, Jul 2025](https://www.edgeprop.sg/property-news/green-premium-nature-raises-housing-prices)) | Places greenery for views, park links and shade buyers value; backs it with resale analysis |
| Cheaper loans | [CDL's S$300M sustainability-linked loan with DBS](https://www.cdl.com.sg/newsroom/cdl-and-dbs-launch-s-300-million-multi-currency-sustainability-linked-loan-to-advance-nature-based-urban-development-solutions-in-singapore) (May 2026) targets microforests and urban farming; a 2023 bank loan to the same developer lowers the rate when targets are met | Monitoring reports supply verified nature data for loan targets |
| Subsidies | [Skyrise Greenery Incentive](https://cuge.nparks.gov.sg/grants/skyrise-greenery-incentive-scheme--sgis-): up to 50% co-funding, capped at $500/m² for green walls | Picks greenery that counts for compliance and qualifies for co-funding |
| Extra floor area | URA lets sky terraces and communal gardens count toward the requirement, some with floor-area exemptions (current terms to verify) | Flags designs that meet the rule and free up floor area |
| Greenery that earns rent | HDB carpark rooftops rented to urban farms; a reported top bid of $90,000/year (2020, unverified) | Turns roof or landscape area into rented farm or garden plots |
| Faster approvals | Hypothesis, no data | Built-in compliance check cuts redesign rounds |

In the tool, each greenery option shows: cost → compliance credit → subsidy → price premium → loan benefit → rent → neighbourhood score. Lead return for the pitch: cheaper loans, since only verified community data can prove nature targets were met.

*Build notes: the Skyrise Greenery Incentive covers existing buildings, so it is modelled as a retrofit revenue line, not a return on new GLS sites. The resale value lens found no within-town premium for block-level canopy, which supports leading with finance rather than sale premium.*

### How it fits the platform

Every greenery feature a user adds is one shared object (location, type, area, compliance credit, index effect, cost and return inputs), so one change updates compliance, scores and returns together.

1. **Index and scenario engine:** scores the site's 400 m neighbourhood before and after the feature.
2. **Compliance check:** reads its area and leaf area against URA's tiers.
3. **Tweak engine:** ranks suggestions on two axes: neighbourhood score gain and financial return.
4. **Return calculator:** sums subsidy, premium, loan benefit and rent, with every assumption shown and adjustable.
5. **Monitoring:** turns post-completion community reports into verified evidence for sustainability-linked loan targets, then feeds back into the index.

### For planners

* **Scenario scoring for new towns:** upload a town plan, compare versions, and see which past towns' designs worked.
* **Inclusion check:** flags plans that leave seniors and rental-flat households poorly served.
* **Access:** professional seats, or an annual government licence bought through tender.

## Sources

* [URA Master Plan 2025: A Cool City in a Warming World](https://www.ura.gov.sg/land-planning/master-plan/master-plan-2025/themes/strengthening-urban-resilience/a-cool-city-in-a-warming-world/)
* [URA greenery requirements for flats and condominiums](https://www.ura.gov.sg/Corporate/Guidelines/Development-Control/Residential/Flats-Condominiums/Greenery)
* [Singapore Green Plan 2030 targets](https://www.greenplan.gov.sg/targets/)
* [Her World: SUTD home-heat study (May 2026)](https://www.herworld.com/life/your-home-hotter-outside-what-singapores-latest-housing-study-reveals)
* [Chew, Chung & Ang: rental-flat thermal inequality (WSBE 2026 abstract)](https://wsbe-2026.p.asnevents.com.au/days/2026-06-11/abstract/130130)
* [Benita, Kalashnikov & Tunçer 2021: Spatial Livability Index](https://ideas.repec.org/a/sae/envirb/v48y2021i7p2006-2022.html)
* [Xu et al. 2025: equity in heat mitigation by green space](https://ideas.repec.org/a/eee/ecoser/v73y2025ics2212041625000312.html)
* [Mothership: Singapore-ETH heat vulnerability hotspots (Feb 2024)](https://mothership.sg/2024/02/spore-hotter-sengkang-hot-wp-motion//amp)
* [npj Urban Sustainability 2025: SE Asian capitals heat 1990–2024](https://www.nature.com/articles/s42949-025-00315-8) (abstract only)
* [Science Centre: which street shade keeps you cool (CARES, one-north)](https://voiddeck.science.edu.sg/articles/environment/street-shade/)
* [World Bank: Walk2Ride 400 m covered walkways (Nov 2018)](https://blogs.worldbank.org/zh/eastasiapacific/livability-start-neighborhood-singapore-stories-part-2)
* [CDL and DBS: S$300M sustainability-linked loan (May 2026)](https://www.cdl.com.sg/newsroom/cdl-and-dbs-launch-s-300-million-multi-currency-sustainability-linked-loan-to-advance-nature-based-urban-development-solutions-in-singapore)
* [EdgeProp: green premium near Jurong Lake Gardens (Jul 2025)](https://www.edgeprop.sg/property-news/green-premium-nature-raises-housing-prices)
* [data.gov.sg Open Data Licence](https://data.gov.sg/open-data-licence)
