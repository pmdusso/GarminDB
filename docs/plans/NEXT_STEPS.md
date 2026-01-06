# Strategic Roadmap: GarminDB Analytical Engine

## current Status
The core health pillars have been implemented following a layered architecture:
- **Sleep:** Quality, consistency, and stage distribution.
- **Stress:** AUC Load calculation and post-activity resilience.
- **Recovery:** Cardiovascular baseline (RHR) and Load balance (ACWR).
- **Activity:** TSB Model (Fitness/Fatigue) and Intensity Distribution (80/20).

All modules are integrated into the `HealthReport` and rendered via `MarkdownPresenter`.

---

## Strategic Directions for Future Development

### 1. Correlation Intelligence (The Brain)
**Goal:** Connect the dots between separate domains to find hidden biological patterns.
- **Concept:** Cross-domain analysis where one metric acts as a predictor for another.
- **Key Features:**
    - Impact of late-night activities on sleep deep/rem phases.
    - Correlation between daily stress load and recovery efficiency.
    - Predictive alerts: "Elevated RHR detected; performance drop likely in 24-48h."
- **Why it matters:** It transforms raw data into actionable biological advice.

### 2. Body Composition & Metabolic Health (The Physical Pillar)
**Goal:** Bring weight, body fat, and hydration into the analytical framework.
- **Concept:** Monitor the physical response to training load and recovery.
- **Key Features:**
    - Muscle mass vs. Training Load trends (detecting overtraining/catabolism).
    - Fat percentage vs. Aerobic Efficiency correlation.
    - Hydration patterns relative to activity intensity.
- **Why it matters:** Provides a physical verification of fitness gains and nutritional adequacy.

### 3. Long-Term Trends & Seasonality (The Big Picture)
**Goal:** Analyze health evolution across months and years.
- **Concept:** Moving beyond the 7-30 day window to track "Macro-Baselines."
- **Key Features:**
    - Year-over-year fitness comparisons (VO2 Max, Pace/HR trends).
    - Seasonal stress patterns (Work/Holiday cycles).
    - Detection of long-term cardiovascular adaptation or chronic fatigue.
- **Why it matters:** Distinguishes between temporary fitness peaks and true health improvements.

---

## Recommendation for Next Phase
Start with **Correlation Intelligence**. We have already built the complex data infrastructure for all pillars; the most valuable next step is to synthesize this data into higher-level insights that no standard fitness app currently provides.
