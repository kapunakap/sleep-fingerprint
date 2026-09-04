# sleep-fingerprint

Research and prototype work for an **under-mattress ballistocardiography (BCG) sensor + sleep foundation model**.

The goal is to explore whether passive overnight mechanical biosignals can learn a stable personal **sleep fingerprint** and support downstream estimates such as age, longitudinal physiological change, and research health-risk signals.

> Research project only. Outputs are not medical diagnoses.

## Inspiration

The project is inspired by recent Eight Sleep research describing a model pretrained on raw bed-based biosignals. Instead of pretraining directly on age or disease labels, the model learned whether two short sleep windows belonged to the same person.

The reported idea is compelling because a same-person contrastive task can force a model to discover stable physiological information such as cardiac mechanics, respiration, autonomic patterns, and overnight dynamics.

Reported launch-post results included:

- Rank-1 person identification: **92.5%**
- age prediction MAE: about **3.3 years**
- diabetes AUROC: **0.852**
- hypertension AUROC: **0.810**
- sleep apnea AUROC: **0.792**
- snoring AUROC: **0.751**
- external heart-failure AUROC: **0.822**

These values should be checked against the final paper/supplement before being treated as canonical benchmarks.

## Important interpretation

A model predicting **chronological age** from physiology with low error is not automatically a validated **biological-age** model.

To make a biological-age claim, we would eventually want evidence that model residuals or trajectories predict meaningful outcomes — health status, function, morbidity, future risk, etc. — beyond chronological age itself.

Likewise, **speed of aging** is inherently longitudinal. A one-night age estimate is not enough.

## Target system

```text
under-mattress sensor
        ↓
raw BCG + respiration + motion waveform
        ↓
analog front end + ADC
        ↓
BLE / Wi-Fi acquisition
        ↓
signal preprocessing + segmentation
        ↓
self-supervised / contrastive encoder
        ↓
person embedding (sleep fingerprint)
        ↓
├─ age model
├─ longitudinal physiological trend
├─ research health classifiers
└─ iPhone app / dashboard
```

## Hardware paths

### A. EMFIT QS Research — fastest serious path

Best option if the priority is getting useful raw BCG data quickly without designing electronics first.

Relevant links:

- https://emfit.com/sleep-research/
- https://emfit.com/sleep-research/emfit-qs-cloud-api/

Why it is interesting:

- contactless under-mattress BCG sensing
- research/raw-signal offering
- raw waveform access suitable for model development
- avoids building an analog acquisition board before proving the ML idea

**Before buying:** confirm in writing that the exact package provides continuous raw waveform access and the required research/API rights. Do not assume the consumer package includes the raw research API.

### B. PolyK / PiezoPVDF 800 mm sleep strip — preferred DIY path

This is the most interesting path if we want to own the complete sensing/data stack.

Candidate links:

- https://piezopvdf.com/long-sleeping-sensor-800mm-breath/
- https://piezopvdf.com/cloth-sleeping-sensor/

The strip is intended to capture mechanical activity caused by heartbeat, respiration, and body movement through the mattress.

Potential acquisition module:

- https://piezopvdf.com/Q-bluetooth/

Before buying the acquisition module, verify:

1. continuous raw sampling rate
2. ADC resolution
3. whether truly raw samples are exposed before vendor filtering
4. Bluetooth Low Energy compatibility with iOS
5. communication protocol documentation
6. timestamp quality / clock drift
7. whether data can stream for an entire night without gaps

### C. Custom acquisition electronics

If the vendor acquisition module is limiting, build our own.

Likely prototype chain:

```text
PVDF strip → input protection → charge/high-Z amplifier → filtering → ADC → ESP32-S3 → BLE/Wi-Fi
```

Candidate controller: **ESP32-S3 DevKitC**.

Important: do **not** connect a PVDF strip directly to a microcontroller ADC. Piezo sensors are high impedance and can generate large transients from movement; proper analog front-end design and input protection are required.

### D. Withings Sleep Analyzer — useful reference, probably not the model input

The Withings Sleep Analyzer is conceptually relevant because it senses sleep mechanically from under the mattress, but it is only useful for this project if we can obtain the **continuous raw BCG waveform**.

Processed sleep summaries alone are not enough for the foundation-model experiment.

## Why a bed sensor instead of only a wearable?

An under-mattress sensor has several attractive properties:

- no charging or wearing behavior
- continuous multi-hour recording
- potentially high adherence over months
- allows session-level and multi-night sequence modeling
- captures mechanical cardiac and respiratory signals that are different from standard optical PPG

A wearable/HealthKit version could still be a useful software MVP, but it would not reproduce the raw BCG setup.

## Model approach

### 1. Raw preprocessing

Start with the raw waveform and preserve it permanently.

Likely pipeline:

```text
raw samples
→ timestamp validation
→ de-trending / filtering
→ motion and saturation detection
→ signal-quality score
→ fixed windows, initially ~60 s
→ normalized training examples
```

Do not throw away raw data after preprocessing. We should be able to rerun every transformation later.

### 2. Sleep-fingerprint pretraining

Do **not** start by training directly on age.

Use a same-person / different-person objective across nights:

```text
window from night A ─┐
                      ├─ shared encoder → embeddings → similarity objective
window from night B ─┘
```

Training objective:

- same person across different nights → embeddings closer
- different people → embeddings farther apart

Potential representation features include:

- cardiac mechanical morphology
- timing of pulse/recoil waves
- respiration depth and rhythm
- heart/respiration coupling
- autonomic patterns
- movement characteristics
- sleep-stage-dependent dynamics

### 3. Identity/retrieval evaluation

Before health tasks, prove the representation actually learns stable person-specific physiology.

Evaluate:

- Rank-1 identification
- top-k retrieval
- same-person verification AUROC
- embedding stability across nights
- robustness to posture
- robustness to sensor placement
- robustness across mattress types
- robustness across hardware revisions

### 4. Age model

Train a chronological-age head on top of the representation.

Report at minimum:

- MAE
- RMSE
- R²
- calibration by age band
- uncertainty/confidence intervals

### 5. Longitudinal model

The product opportunity is more interesting than a one-time age guess.

Long-term question:

> Is a person's physiological sleep signature becoming persistently "younger" or "older" over months?

Target 30+ consecutive nights per person and model a stable personal baseline plus persistent changes.

### 6. Research health heads

Only after the representation is validated, test downstream research labels such as:

- sleep apnea / snoring
- hypertension
- metabolic risk
- heart-related conditions

These are research classifiers unless and until they receive appropriate clinical validation and regulatory treatment.

## Validation rules

Leakage is the easiest way to accidentally produce impressive but meaningless results.

Non-negotiable rules:

- split datasets by **person**, not by window or night
- all nights from one participant stay in exactly one split
- evaluate on participants never seen during training
- keep a final untouched test set
- use external cohorts where possible
- report confidence intervals
- benchmark simple baselines
- log every preprocessing/model version
- track sensor placement, mattress, hardware revision, and firmware
- test for demographic and hardware-domain shifts

## Data collection metadata

Every recording should ideally include:

- anonymous participant ID
- hardware revision
- firmware version
- sampling rate
- start/end timestamps
- packet/dropout information
- sensor placement
- mattress type / approximate thickness
- occupancy state
- optional posture annotations
- optional wearable reference data
- optional known age/sex labels with consent

Raw biosignals and identity metadata should be stored separately where practical.

## Privacy and security

A model capable of identifying a person from sleep signals should be treated as handling **biometric-like sensitive data**.

Design for:

- explicit informed consent
- encryption in transit and at rest
- minimal personally identifiable information
- deletion/export controls
- clear retention policy
- access logging
- separate identity mapping from signal storage
- no diagnostic marketing without adequate validation

## MVP roadmap

### Phase 0 — prove the sensor

- [ ] Choose EMFIT Research or DIY PVDF for the first recording
- [ ] Confirm continuous raw waveform access
- [ ] Capture one complete night
- [ ] Verify visible heartbeat structure
- [ ] Verify respiration structure
- [ ] quantify dropouts / clipping / motion artifacts
- [ ] save raw samples and metadata reproducibly

### Phase 1 — acquisition pipeline

- [ ] define raw file format
- [ ] define timestamps and clock synchronization
- [ ] build signal-quality metrics
- [ ] build motion/artifact detection
- [ ] build reproducible filtering/segmentation
- [ ] visualize raw vs processed BCG
- [ ] create overnight QA report

### Phase 2 — multi-night dataset

- [ ] collect several nights per participant
- [ ] support multiple participants
- [ ] consent + anonymized IDs
- [ ] dataset versioning
- [ ] participant-level train/val/test split tooling

### Phase 3 — sleep fingerprint

- [ ] train contrastive encoder
- [ ] measure Rank-1 / top-k identification
- [ ] measure same-person verification
- [ ] inspect embedding stability
- [ ] test placement/posture robustness

### Phase 4 — age model

- [ ] train age head
- [ ] participant-level evaluation
- [ ] MAE / RMSE / R²
- [ ] calibration and uncertainty
- [ ] compare against simple signal-feature baselines

### Phase 5 — longitudinal model

- [ ] collect 30+ consecutive nights
- [ ] learn stable individual baseline
- [ ] distinguish persistent trend from nightly noise
- [ ] evaluate reproducibility of trend metrics

### Phase 6 — iPhone app

- [ ] onboarding
- [ ] sensor provisioning
- [ ] nightly recording status
- [ ] signal-quality diagnostics
- [ ] sleep-fingerprint view
- [ ] age estimate + uncertainty
- [ ] longitudinal trend
- [ ] data export/delete
- [ ] explicit research/non-diagnostic language

## First purchase decision

Two sensible starting points:

1. **Fastest research path:** EMFIT QS Research with confirmed raw waveform access.
2. **Own the full stack:** protected 800 mm PolyK/PiezoPVDF sleep strip plus an acquisition module or custom analog front end.

The current preference for a long-term product is **Option 2**, but Option 1 may be the fastest way to validate the ML/data pipeline before investing in custom electronics.

## Immediate next step

Before spending significant time on the app or model:

> **Get one full night of high-quality raw BCG into a file we control.**

Everything else depends on that.