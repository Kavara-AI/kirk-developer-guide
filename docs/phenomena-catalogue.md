# What does your data look like?

<!-- Generated from catalogues/phenomena.json. Edit that source, then run
python3 scripts/render_phenomena_catalogue.py. -->

Explore **256 candidate phenomena across 32 domains**. Find data that
resembles yours, then follow its preparation questions. You do not need to know
what you will discover or what you will do with it before exploring.

**Hypothesis — applies to every example below.** These are exploration prompts,
not demonstrated Kirk capabilities or a fixed taxonomy of phenomenon labels.
The categories are navigation aids; choose several or none. Keep room for
unclassified discoveries. Kirk's role is identifying phenomena; interpretation
and action are separate. No example establishes diagnosis, prediction or causality.

A domain match does not establish model fit. The actual representation must match
the selected model's documented **data envelope** (input contract). This page
does not expand the currently documented API to arbitrary files or data shapes.
Read [capability fit](capability-fit.md) and the
[proposed upload-and-data-fit handoff](tensor-generation.md#proposed-upload-and-data-fit-handoff).

## Browse by domain

- [Financial markets](#financial-markets)
- [Payments and transaction networks](#payments)
- [Insurance](#insurance)
- [Retail and commerce](#retail)
- [Product and customer behavior](#product-behavior)
- [Software systems](#software)
- [Cybersecurity](#cybersecurity)
- [Telecommunications and networks](#telecommunications)
- [Computing hardware and data centres](#computing-hardware)
- [Manufacturing](#manufacturing)
- [Machinery and industrial equipment](#machinery)
- [Materials and chemistry](#materials-chemistry)
- [Energy generation and electricity grids](#energy)
- [Batteries and electrochemical systems](#batteries)
- [Buildings and cities](#buildings-cities)
- [Road transport and mobility](#road-transport)
- [Logistics and supply chains](#logistics)
- [Aviation and maritime operations](#aviation-maritime)
- [Space systems and astronomy](#space-astronomy)
- [Weather and climate](#weather-climate)
- [Oceans and water systems](#oceans-water)
- [Geology and the subsurface](#geology)
- [Ecology and biodiversity](#ecology)
- [Agriculture and food production](#agriculture)
- [Human physiology](#physiology)
- [Neuroscience and behavior](#neuroscience)
- [Genomics and cellular biology](#genomics)
- [Public health and population dynamics](#public-health)
- [Language, communication and information](#language-information)
- [Education and learning](#education)
- [Sport, movement and performance](#sport-movement)
- [Music, sound and creative media](#music-media)

## Recognize the structure of your data

These profiles describe source data, not supported Kirk inputs or automatic
transformations. Confirm their meaning with the data owner before preprocessing.

<a id="time-series"></a>
### Measurements over time

- What does each observation measure, in which units, and for which entity?
- Are timestamps regular, irregular or asynchronous across channels?
- Which gaps, exact zeros, resets and changes in collection practice must remain distinguishable?

**Preparation:** Preserve timestamps and channel identities. Document alignment, units and missingness before choosing any resampling or scaling.

<a id="event-sequences"></a>
### Timestamped events

- What defines an event, its identity and its occurrence time versus its arrival time?
- Are repeated events duplicates or genuine repetitions?
- Which entity and session boundaries must be preserved?

**Preparation:** Keep event order, elapsed time and entity boundaries. Any binning or aggregation needs a stated rule and a check that it preserves the phenomena of interest.

<a id="relationships"></a>
### Relationships and networks

- What do nodes, edges, directions and weights mean?
- Do entities or relationships appear, disappear or change identity?
- Are observations individual events or network snapshots?

**Preparation:** Preserve entity mappings and relationship semantics. A graph-to-observation representation requires its own documented and tested input contract.

<a id="spatial-panels"></a>
### Measurements across locations

- What are the coordinates, coordinate system, resolution and any depth or altitude axes?
- Are locations fixed, moving or sampled unevenly?
- Which observations are simultaneous and which only appear in the same file?

**Preparation:** Retain coordinates, measurement support, time and coverage. Do not treat arbitrary row or location order as chronology.

<a id="repeated-runs"></a>
### Repeated experiments or operating cycles

- What defines a run, cycle, subject or batch boundary?
- Do sampling rates, durations or experimental conditions differ?
- Which measurements were available at each point within a run?

**Preparation:** Retain run boundaries and conditions. Specify alignment and state reset policy; do not concatenate independent runs into an invented continuous history.

<a id="encoded-media"></a>
### Numerical representations of text, images or audio

- Which numerical representation or feature extractor is proposed, and what is its version?
- Which temporal, spatial or semantic relationships does that representation preserve or discard?
- Are feature definitions stable across the proposed dataset?

**Preparation:** Record representation provenance and retained axes. A numerical encoding is not proof of Kirk compatibility or a useful embedding; verify a matching input contract.

<a id="unordered-samples"></a>
### Unordered samples or static tables

- Are rows independent samples, or is there a genuine temporal or spatial order?
- Which sample, batch and feature identities matter?
- Would the proposed representation introduce an artificial ordering?

**Preparation:** Preserve sample and batch identities. Do not invent a time axis or interpret an inferred ordering as observed chronology; suitability needs separate assessment.

## Exploration prompts

<a id="financial-markets"></a>
### Financial markets

**Example observations:** Timestamped prices, volumes, quotes or other market measurements with instrument identities and units.

**Preparation questions:** [Measurements over time](#time-series); [Timestamped events](#event-sequences).

**Hypotheses to explore:**

- Assets beginning to move together after historically behaving independently.
- Previously correlated assets separating.
- Recurring sequences of volatility, volume and price movement.
- Relationships that appear only during unusually large movements.
- Patterns recurring at different timescales.
- Changes in which instruments lead or lag others.
- Groups of securities exhibiting a shared pattern hidden in market averages.
- Similar market configurations recurring years apart.

<a id="payments"></a>
### Payments and transaction networks

**Example observations:** Dated transactions, account or entity identifiers, amounts and directed relationships, with sensitive identifiers handled appropriately.

**Preparation questions:** [Timestamped events](#event-sequences); [Relationships and networks](#relationships).

**Hypotheses to explore:**

- Recurring sequences of transfers between groups of accounts.
- Changes in the timing between receiving and sending funds.
- Transaction clusters that appear and disappear together.
- Payment behavior with unexpected periodicity.
- Relationships between transaction size, frequency and destination.
- Different accounts developing similar transaction signatures.
- Network structures that recur across otherwise unrelated groups.
- Changes in how activity is distributed across a payment network.

<a id="insurance"></a>
### Insurance

**Example observations:** Claim and policy event histories, exposure measurements, locations and clearly defined observation times.

**Preparation questions:** [Timestamped events](#event-sequences); [Measurements over time](#time-series); [Measurements across locations](#spatial-panels).

**Hypotheses to explore:**

- Claims arriving in recurring temporal clusters.
- Changes in relationships between claim frequency and claim size.
- Similar claim trajectories across different policy populations.
- Geographic patterns in claims that emerge or dissolve.
- Unusual sequences of policy changes and subsequent claims.
- Changes in how long claims remain in different processing states.
- Groups of claims sharing previously unrecognized numerical characteristics.
- Recurring patterns across combinations of exposure, weather and reported loss.

<a id="retail"></a>
### Retail and commerce

**Example observations:** Product, store or customer event histories with timestamps, quantities, prices and availability.

**Preparation questions:** [Timestamped events](#event-sequences); [Measurements over time](#time-series).

**Hypotheses to explore:**

- Products that begin being purchased together.
- Purchasing sequences that recur across different customer groups.
- Changes in relationships between browsing and purchasing.
- Demand patterns shared across apparently unrelated products.
- Differences between local store behavior and aggregate sales.
- Recurring patterns in returns, exchanges and repeat purchases.
- Changes in the timing between purchases.
- Patterns that occur at particular combinations of price, availability and season.

<a id="product-behavior"></a>
### Product and customer behavior

**Example observations:** Timestamped interactions with stable feature and session definitions; identity and coverage policies recorded.

**Preparation questions:** [Timestamped events](#event-sequences); [Measurements over time](#time-series).

**Hypotheses to explore:**

- Recurring paths through an application.
- New sequences of feature usage.
- Groups of users developing similar activity rhythms.
- Changes in how features are used together.
- Periods when overall activity stays stable but its composition changes.
- Repeated transitions between intensive and intermittent use.
- Different user populations converging toward similar behavior.
- Previously common interaction patterns gradually disappearing.

<a id="software"></a>
### Software systems

**Example observations:** Service metrics, request histories and event counts with aligned clocks and service identities.

**Preparation questions:** [Measurements over time](#time-series); [Timestamped events](#event-sequences); [Relationships and networks](#relationships).

**Hypotheses to explore:**

- Recurring combinations of latency, traffic and resource consumption.
- Services whose performance begins moving together.
- Changes in the relationship between workload and response time.
- Repeated sequences of log-event counts.
- Latency patterns confined to particular request types.
- Resource oscillations at unexpected timescales.
- Different deployments producing similar operational signatures.
- Changes in how variability propagates between services.

<a id="cybersecurity"></a>
### Cybersecurity

**Example observations:** Authentication, host and network event histories with entity identities and documented collection coverage.

**Preparation questions:** [Timestamped events](#event-sequences); [Relationships and networks](#relationships); [Measurements over time](#time-series).

**Hypotheses to explore:**

- Recurring sequences of authentication events.
- Machines developing unusually similar activity patterns.
- Changes in relationships between access frequency, timing and volume.
- New patterns of communication between groups of hosts.
- Low-volume activity with persistent temporal structure.
- Different accounts exhibiting synchronized changes.
- Recurring combinations of endpoint and network events.
- Activity structures that differ from a system's established background.

<a id="telecommunications"></a>
### Telecommunications and networks

**Example observations:** Time-indexed traffic, connection-quality and network-location measurements with topology context.

**Preparation questions:** [Measurements over time](#time-series); [Relationships and networks](#relationships); [Measurements across locations](#spatial-panels).

**Hypotheses to explore:**

- Changes in relationships between traffic, latency and packet loss.
- Recurring congestion patterns across network segments.
- Groups of cells exhibiting synchronized load changes.
- Unexpected periodicity in connection quality.
- Changes in traffic composition despite stable total volume.
- Repeated patterns in handovers between mobile cells.
- Geographic clusters of similar signal behavior.
- Changes in which network measurements lead or lag others.

<a id="computing-hardware"></a>
### Computing hardware and data centres

**Example observations:** Power, thermal and performance telemetry with workload, device and run identities.

**Preparation questions:** [Measurements over time](#time-series); [Repeated experiments or operating cycles](#repeated-runs).

**Hypotheses to explore:**

- Recurring relationships between power, temperature and workload.
- Different machines developing similar performance signatures.
- Changes in the relationship between memory traffic and execution time.
- Thermal oscillations across groups of components.
- Workloads with recurring resource-consumption shapes.
- Changes in the distribution of performance across nominally identical hardware.
- Coupled behavior between cooling systems and compute equipment.
- Repeated transitions between distinct operating patterns.

<a id="manufacturing"></a>
### Manufacturing

**Example observations:** Process measurements and output observations with batch, line, stage and time identities.

**Preparation questions:** [Measurements over time](#time-series); [Repeated experiments or operating cycles](#repeated-runs); [Timestamped events](#event-sequences).

**Hypotheses to explore:**

- Recurring combinations of pressure, temperature, speed and output measurements.
- Differences between production lines processing the same product.
- Batch patterns hidden by average quality measurements.
- Changes in relationships between process stages.
- Repeated sequences preceding measurable changes in output.
- Production cycles that gradually change shape.
- Groups of sensors moving together only under particular operating conditions.
- Similar process signatures appearing across different factories.

<a id="machinery"></a>
### Machinery and industrial equipment

**Example observations:** Vibration, load and thermal measurements with sampling rates and machine or cycle identities.

**Preparation questions:** [Measurements over time](#time-series); [Repeated experiments or operating cycles](#repeated-runs).

**Hypotheses to explore:**

- Recurring vibration signatures.
- Changes in relationships between vibration, load and temperature.
- Operating patterns shared by different machines.
- New periodic components in sensor streams.
- Repeated transitions between stable operating patterns.
- Changes in how equipment responds to similar loads.
- Brief events that recur with a consistent internal sequence.
- Differences between apparently identical operating cycles.

<a id="materials-chemistry"></a>
### Materials and chemistry

**Example observations:** Spectra, process trajectories or spatial measurements with sample identities, units and experimental conditions.

**Preparation questions:** [Repeated experiments or operating cycles](#repeated-runs); [Measurements over time](#time-series); [Measurements across locations](#spatial-panels).

**Hypotheses to explore:**

- Recurring structures in spectroscopy measurements.
- Changes in relationships between temperature, pressure and measured properties.
- Distinct reaction-trajectory shapes.
- Repeated sequences during heating and cooling cycles.
- Groups of material samples sharing unusual measurement signatures.
- Changes in relationships between composition and observed response.
- Spatial patterns in material measurements.
- Similar experimental trajectories arising from different starting conditions.

<a id="energy"></a>
### Energy generation and electricity grids

**Example observations:** Demand, generation and grid measurements with location, cadence and equipment context.

**Preparation questions:** [Measurements over time](#time-series); [Relationships and networks](#relationships); [Measurements across locations](#spatial-panels).

**Hypotheses to explore:**

- Recurring combinations of demand, generation and frequency measurements.
- Regions whose electricity consumption begins moving together.
- Changes in relationships between weather and generation output.
- Repeated oscillations across grid measurements.
- Local patterns hidden within system-wide demand.
- Changes in the timing between demand and generation movements.
- Distinct operating patterns across renewable-generation sites.
- Similar grid configurations recurring under different calendar conditions.

<a id="batteries"></a>
### Batteries and electrochemical systems

**Example observations:** Voltage, current and temperature histories with cell, pack and charge-cycle identifiers.

**Preparation questions:** [Measurements over time](#time-series); [Repeated experiments or operating cycles](#repeated-runs).

**Hypotheses to explore:**

- Recurring charge and discharge curve shapes.
- Changes in relationships between voltage, current and temperature.
- Cells diverging from others within the same pack.
- Repeated transitions between different response patterns.
- Changes in recovery behavior after load removal.
- Similar trajectories across batteries with different usage histories.
- Differences between short-term and long-term cycling patterns.
- Groups of cells exhibiting synchronized variability.

<a id="buildings-cities"></a>
### Buildings and cities

**Example observations:** Occupancy, utility, environmental or movement observations with time and location context.

**Preparation questions:** [Measurements over time](#time-series); [Measurements across locations](#spatial-panels); [Timestamped events](#event-sequences).

**Hypotheses to explore:**

- Recurring relationships between occupancy, temperature and energy use.
- Buildings with similar daily operating signatures.
- Changes in how indoor conditions respond to outdoor conditions.
- Neighborhood activity patterns at different timescales.
- Repeated interactions between ventilation, humidity and air-quality measurements.
- Water-consumption patterns shared across locations.
- Distinct combinations of transport, electricity and pedestrian activity.
- Changes in the synchronization of activity across parts of a city.

<a id="road-transport"></a>
### Road transport and mobility

**Example observations:** Time-indexed movement, road-segment or journey observations with spatial and sampling definitions.

**Preparation questions:** [Measurements over time](#time-series); [Measurements across locations](#spatial-panels); [Timestamped events](#event-sequences).

**Hypotheses to explore:**

- Recurring traffic-flow shapes.
- Locations whose congestion patterns become coupled.
- Changes in relationships between speed, density and travel time.
- Repeated sequences of congestion spreading between road segments.
- Travel patterns that recur across different cities.
- Differences between aggregate traffic and individual route behavior.
- Changes in journey-time variability without changes in the average.
- New temporal patterns in charging, parking or vehicle movement.

<a id="logistics"></a>
### Logistics and supply chains

**Example observations:** Shipment, inventory and order histories with item, route, stage and event-time identities.

**Preparation questions:** [Timestamped events](#event-sequences); [Relationships and networks](#relationships); [Measurements over time](#time-series).

**Hypotheses to explore:**

- Recurring sequences of delays across transport stages.
- Suppliers whose delivery patterns begin moving together.
- Changes in relationships between order volume and fulfillment time.
- Repeated shapes in inventory accumulation and depletion.
- Routes exhibiting similar timing signatures.
- Differences between individual-item flows and aggregate shipment volumes.
- Changes in the timing between demand, ordering and replenishment.
- Network-wide patterns emerging from otherwise ordinary local events.

<a id="aviation-maritime"></a>
### Aviation and maritime operations

**Example observations:** Vehicle telemetry, journey histories and environmental observations with equipment and location context.

**Preparation questions:** [Measurements over time](#time-series); [Repeated experiments or operating cycles](#repeated-runs); [Measurements across locations](#spatial-panels).

**Hypotheses to explore:**

- Recurring combinations of engine and environmental measurements.
- Changes in relationships between fuel use, speed and operating conditions.
- Similar trajectories across different aircraft or vessels.
- Repeated patterns in port or airport congestion.
- Changes in the timing between successive operational stages.
- Distinct sensor patterns during apparently similar journeys.
- Coordinated changes across fleets.
- Recurring combinations of movement, weather and equipment behavior.

<a id="space-astronomy"></a>
### Space systems and astronomy

**Example observations:** Instrument measurements, light curves or telemetry with cadence, calibration and observation identities.

**Preparation questions:** [Measurements over time](#time-series); [Measurements across locations](#spatial-panels); [Numerical representations of text, images or audio](#encoded-media).

**Hypotheses to explore:**

- Repeating structures in light curves.
- Unusual sequences in spacecraft telemetry.
- Changes in relationships between onboard measurements.
- Similar observational signatures across different astronomical objects.
- Patterns recurring at multiple observation timescales.
- Groups of signals varying together across instruments.
- Transient observations with recurring numerical shapes.
- Changes in background measurement distributions.

<a id="weather-climate"></a>
### Weather and climate

**Example observations:** Atmospheric measurements with station or grid coordinates, units, cadence and coverage.

**Preparation questions:** [Measurements over time](#time-series); [Measurements across locations](#spatial-panels).

**Hypotheses to explore:**

- Recurring combinations of atmospheric measurements.
- Distant locations exhibiting similar temporal patterns.
- Changes in relationships between temperature, humidity, pressure and wind.
- Seasonal patterns changing in timing or shape.
- Persistent configurations within multivariate weather data.
- Repeated sequences across transitions between weather conditions.
- Local patterns obscured by regional averages.
- Relationships appearing mainly during extreme observations.

<a id="oceans-water"></a>
### Oceans and water systems

**Example observations:** Flow, level, temperature, salinity or quality observations with station, depth and timestamp metadata.

**Preparation questions:** [Measurements over time](#time-series); [Measurements across locations](#spatial-panels).

**Hypotheses to explore:**

- Recurring combinations of temperature, salinity and current measurements.
- Changes in relationships between river flow and water-quality measurements.
- Similar water-system behavior across different catchments.
- Repeated sequences in reservoir levels and inflows.
- Spatially coordinated changes across monitoring stations.
- New periodicity in tidal or coastal measurements.
- Different layers of a water column beginning to behave similarly.
- Persistent patterns within otherwise variable sensor streams.

<a id="geology"></a>
### Geology and the subsurface

**Example observations:** Geophysical, well or survey measurements with location, depth, cadence and instrument context.

**Preparation questions:** [Measurements over time](#time-series); [Measurements across locations](#spatial-panels); [Repeated experiments or operating cycles](#repeated-runs).

**Hypotheses to explore:**

- Recurring seismic waveform structures.
- Changes in relationships between deformation and other measurements.
- Spatial clusters of similar geophysical signals.
- Repeated combinations of pressure, flow and temperature in wells.
- Distinct patterns within borehole measurements.
- Similar event sequences across different locations.
- Changes in background vibration or acoustic activity.
- Multiscale structures within geological survey data.

<a id="ecology"></a>
### Ecology and biodiversity

**Example observations:** Species, habitat or movement observations with survey effort, location and timestamp context.

**Preparation questions:** [Measurements over time](#time-series); [Measurements across locations](#spatial-panels); [Relationships and networks](#relationships).

**Hypotheses to explore:**

- Species populations developing synchronized patterns.
- Changes in relationships between species counts and environmental measurements.
- Recurring structures in animal movement.
- Seasonal activity patterns changing in timing.
- Groups of habitats exhibiting similar dynamics.
- Repeated combinations of abundance, diversity and environmental conditions.
- Spatial patterns in ecosystem observations.
- Previously stable relationships between ecological measurements weakening.

<a id="agriculture"></a>
### Agriculture and food production

**Example observations:** Field, livestock or production measurements with location, batch, season and sampling context.

**Preparation questions:** [Measurements over time](#time-series); [Measurements across locations](#spatial-panels); [Repeated experiments or operating cycles](#repeated-runs).

**Hypotheses to explore:**

- Recurring combinations of soil moisture, temperature and crop measurements.
- Fields developing similar growth trajectories.
- Differences within a field that persist across observations.
- Changes in relationships between environmental conditions and plant measurements.
- Repeated sensor patterns across growing seasons.
- Livestock groups exhibiting shared activity rhythms.
- Distinct trajectories in fermentation or food-processing measurements.
- Similar patterns across different crops, locations or production systems.

<a id="physiology"></a>
### Human physiology

**Example observations:** Consented multichannel physiological measurements with units, cadence, activity context and subject boundaries.

**Preparation questions:** [Measurements over time](#time-series); [Repeated experiments or operating cycles](#repeated-runs).

**Hypotheses to explore:**

- Recurring combinations of heart rate, movement and temperature.
- Changes in relationships between physiological measurements.
- Individual rhythms that differ from population averages.
- Repeated response shapes following similar activities.
- Changes in coordination between different physiological signals.
- Patterns that appear only during particular combinations of activity and rest.
- Similar physiological trajectories across different individuals.
- Short-lived events with repeatable multichannel signatures.

<a id="neuroscience"></a>
### Neuroscience and behavior

**Example observations:** Recorded neural or behavioral measurements with channel identities, trial boundaries and sampling context.

**Preparation questions:** [Measurements over time](#time-series); [Repeated experiments or operating cycles](#repeated-runs); [Relationships and networks](#relationships).

**Hypotheses to explore:**

- Recurring patterns of neural activity.
- Changes in synchronization between recorded channels.
- Repeated transitions between numerical activity patterns.
- Relationships between movement and neural measurements.
- Similar response trajectories across different experimental conditions.
- Changes in the timing between signals from different regions.
- Multiscale structures in electrophysiological recordings.
- Stable patterns embedded within otherwise variable activity.

<a id="genomics"></a>
### Genomics and cellular biology

**Example observations:** Molecular or cellular measurements with sample identities, batch context and genuine time labels where available.

**Preparation questions:** [Unordered samples or static tables](#unordered-samples); [Measurements over time](#time-series); [Repeated experiments or operating cycles](#repeated-runs).

**Hypotheses to explore:**

- Groups of genes whose expression varies together.
- Changes in relationships between molecular measurements.
- Repeated trajectories through measured cellular states.
- Rare numerical profiles within large cell populations.
- Similar response patterns across different experimental conditions.
- Relationships that appear only within particular cell populations.
- Recurring temporal structures in protein or metabolite measurements.
- Differences between population averages and subgroup behavior.

<a id="public-health"></a>
### Public health and population dynamics

**Example observations:** Population-level observations with denominators, region identities, observation dates and reporting delays.

**Preparation questions:** [Measurements over time](#time-series); [Measurements across locations](#spatial-panels); [Timestamped events](#event-sequences).

**Hypotheses to explore:**

- Recurring geographic patterns in recorded events.
- Regions with similar time-dependent trajectories.
- Changes in relationships between environmental and population measurements.
- Repeated sequences in healthcare demand.
- Differences between local patterns and national aggregates.
- Changes in the synchronization of observations across regions.
- Seasonal structures shifting in timing or intensity.
- Groups of indicators exhibiting shared patterns across different populations.

<a id="language-information"></a>
### Language, communication and information

**Example observations:** Numerical content representations or communication metadata with source, ordering and representation versions.

**Preparation questions:** [Numerical representations of text, images or audio](#encoded-media); [Timestamped events](#event-sequences); [Relationships and networks](#relationships).

**Hypotheses to explore:**

- Recurring trajectories through numerical representations of topics.
- Changes in relationships between topics across document streams.
- Groups of sources developing similar publication patterns.
- Repeated structures in conversation timing and turn-taking.
- Changes in how information propagates through a network.
- Similar document-sequence patterns across different communities.
- Persistent numerical structures within otherwise changing content.
- Differences between aggregate discourse and smaller community patterns.

<a id="education"></a>
### Education and learning

**Example observations:** Learning interactions and task measurements with session, task-version and learner boundaries.

**Preparation questions:** [Timestamped events](#event-sequences); [Measurements over time](#time-series); [Repeated experiments or operating cycles](#repeated-runs).

**Hypotheses to explore:**

- Recurring sequences of problem-solving attempts.
- Groups of learners exhibiting similar learning trajectories.
- Changes in relationships between time spent and observed task performance.
- Repeated transitions between different interaction patterns.
- Distinct response-time patterns across task types.
- Similar learning sequences appearing in different subjects.
- Patterns in revisiting, skipping and repeating material.
- Differences between group averages and individual progress shapes.

<a id="sport-movement"></a>
### Sport, movement and performance

**Example observations:** Movement, activity and performance measurements with participant, session and spatial context.

**Preparation questions:** [Measurements over time](#time-series); [Repeated experiments or operating cycles](#repeated-runs); [Measurements across locations](#spatial-panels).

**Hypotheses to explore:**

- Recurring movement sequences.
- Changes in coordination between measured body segments.
- Athletes exhibiting similar workload-response trajectories.
- Repeated patterns in team movement.
- Relationships between pace, effort and environmental conditions.
- Changes in performance variability despite stable averages.
- Distinct patterns across repeated training sessions.
- Similar tactical configurations appearing in different matches.

<a id="music-media"></a>
### Music, sound and creative media

**Example observations:** Numerical audio, image or motion representations with sample rates, sequence boundaries and extractor versions.

**Preparation questions:** [Numerical representations of text, images or audio](#encoded-media); [Measurements over time](#time-series); [Repeated experiments or operating cycles](#repeated-runs).

**Hypotheses to explore:**

- Recurring structures in numerical audio representations.
- Relationships between rhythm, intensity and spectral measurements.
- Similar temporal shapes across different recordings.
- Changes in coordination between musical parts.
- Repeated visual patterns across image or video sequences.
- Multiscale structures in motion, color or composition measurements.
- Unusual combinations of otherwise familiar features.
- Patterns shared across works that belong to different labeled genres.

## Continue with your data

Use the [data-fit handoff](tensor-generation.md#proposed-upload-and-data-fit-handoff)
to record what your observations mean and what remains unknown. Then build
an [evidence-backed phenomena catalogue](phenomena-discovery.md#build-an-evidence-backed-catalogue)
from actual results; this inspiration list is not that result catalogue.

The machine-readable source is [catalogues/phenomena.json](../catalogues/phenomena.json).
It supports reuse in a proposed intake/preprocessing suite. It contains no
detectors, learned parameters, automatic fit decisions or upload service.
