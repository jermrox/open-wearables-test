# Vybe Data Source Policy

## Product principle

Vybe is not a wearable aggregator for competitor devices. The platform exists to make Vybe's own sensing and intelligence infrastructure extensible while enriching it with non-competitive health and contextual data.

## First-party / proprietary source

- Vybe Band and future Vybe hardware
- Vybe firmware
- Vybe signal processing
- Vybe calibration and sensor fusion
- Vybe-derived physiological features

These remain proprietary and are exposed only through controlled normalized SDK/API capabilities.

## Approved external source classes

External integrations may be built when they add health or contextual information without turning Vybe into a compatibility layer for competing wearable products. Examples include:

- Apple Health / HealthKit
- Google Health Connect
- FHIR / medical-record systems
- laboratory data
- pharmacy / medication data
- nutrition data
- training/workout context where explicitly approved
- environmental and location-derived context
- calendars and user-entered context where explicitly approved
- other clinical or health infrastructure approved by Vybe

## Competitor wearable exclusion

Do not build first-party source adapters for competing wearable platforms unless Vybe explicitly changes this policy.

Excluded examples include:

- Oura
- WHOOP
- Garmin wearable data
- Fitbit wearable data
- Polar wearable data
- Ultrahuman
- Suunto wearable data
- other direct wearable competitors

Existing upstream Open Wearables code for these providers is inherited reference material only and is not part of the Vybe target architecture.

## Architecture implication

Generic provider, OAuth, webhook, retry, checkpoint, normalization, provenance, and storage infrastructure may remain because those capabilities are required for approved non-competitor sources. Vendor-specific competitor adapters must not be registered in the Vybe runtime or exposed in the commercial SDK/API.

## SDK positioning

Open platform, proprietary engine:

- Developers build on Vybe's normalized data and approved capabilities.
- Developers do not receive firmware, raw protocol internals, calibration constants, proprietary signal-processing code, or algorithm implementations.
- External health/context integrations enrich Vybe; they do not make Vybe dependent on competitor wearable ecosystems.
