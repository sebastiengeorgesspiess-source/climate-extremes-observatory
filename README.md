# Climate Extremes & Earth System Observatory 2.2.0

## 11 September 2026 · 2.2.0

See [the dated release notes](RELEASE-20260911.md) for the reviewed changes and verification. Zenodo archival updates are pending; existing DOI links identify their older archived versions, not this source update.

An interactive country-level physical-climate evidence system by Sebastien Spiess.

Live application: https://sebastienspiess.ch/climate/

Archived release: https://doi.org/10.5281/zenodo.22175808

## Scope

The observatory separates observed physical climate, scenario-conditioned projections and model uncertainty. It does not calculate a composite climate-risk score, attribute individual events automatically, or combine physical change with social vulnerability. Human-system consequences belong to the separate Humanity Futures Observatory.

## Data

- World Bank CCKP ERA5 0.25° country aggregates, 1950–2025 (DOI: 10.57966/128g-6s70)
- World Bank CCKP bias-corrected CMIP6 0.25° ensemble products
- NASA/NSIDC PyGEM-OGGM glacier projections V001 (DOI: 10.5067/P8BN9VO9N5C7)
- NASA GISTEMP v4, NOAA GML, NOAA NCEI, NSIDC Sea Ice Index v4, IPCC AR6 and WMO assessments

Missing values are retained as missing. National aggregates must not be interpreted as local observations. Projections are conditional on emissions pathways and are not forecasts.

## Release contents

- `app.py`: server-side data retrieval, caching and export logic
- `templates/intelligence.html`: application interface
- `static/country-profile-v3.js`: country-profile interaction and rendering
- `METHODS.md`: scientific design and limitations
- `PEER_REVIEW_PROTOCOL.md`: independent review checklist
- `CHANGELOG.md`: release history
- `MANIFEST.sha256`: file checksums

## Citation

Spiess, Sebastien (2026). Climate Extremes & Earth System Observatory, version 2.0.0. Zenodo. https://doi.org/10.5281/zenodo.22175808

## Source archive boundaries

Shared site assets and external datasets are not bundled. Use your own restricted browser map key where `YOUR_CARTO_BROWSER_KEY` appears. The DOI above identifies the older 2.0.0 archive, not this 2.2.0 source. The measured sea-level addition and its transformation are described in the dated release notes.
