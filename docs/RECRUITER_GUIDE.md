# Recruiter evidence guide — RailFlow ML Data Platform

[**Full case study on Mulero Analytics**](https://tosinmulero.github.io/data-analytics-portfolio/case-studies/railflow-ml-data-platform.html) · [Repository README](../README.md) · [Main portfolio](https://tosinmulero.github.io/data-analytics-portfolio/projects.html)

> **Data provenance:** Uses an Office of Rail and Road station usage reporting release, with documented processing and cross-sectional modelling limits.

## The question

How can rail station data be transformed, quality-checked, modelled and served using reproducible data engineering, MLOps and secure cloud deployment?

## Technical approach

- Raw → Bronze → Silver → Gold, dbt marts and feature-store preparation.
- Airflow orchestration and MLflow-based model registration.
- Validated artefact serving using FastAPI/Docker, GitHub Actions and Terraform/AWS.

## Documented results to review

- 2,595 Bronze records processed; 2,593 validated curated station records.
- 29 dbt build passes and 38 pytest passes recorded.
- 25 Terraform-managed AWS resources; end-to-end ECS/Fargate deployment checks documented.

## Evidence map

| Review item | Source | What it supports |
|---|---|---|
| Platform architecture | [Open](../docs/architecture/railflow-platform.md) | Architecture and security boundaries |
| Deployment evidence | [Open](../docs/deployment-evidence.md) | Recorded cloud checks |
| Model evidence visual | [Open](../docs/screenshots/03_model_evidence.svg) | Model review summary |
| Portfolio project summary | [Open](../docs/portfolio-summary.md) | Readable technical scope |

## Reproducibility and limitations

Follow the README for local environment, pipeline, test and deployment prerequisites. The cloud demonstration was verified but its infrastructure is intentionally ephemeral. A single annual release does not support future time-series forecasting.

The repository README and linked source files remain the primary technical record. Numbers in this guide summarise the documented project artefacts; they are not claims of a third-party deployment, independently verified business impact or a live customer engagement.

## Reviewer path

1. Scan the [portfolio case study](https://tosinmulero.github.io/data-analytics-portfolio/case-studies/railflow-ml-data-platform.html) for the problem and conclusions.
2. Open the main visual and supporting artefacts from the evidence map.
3. Review the repository README for tooling, methods, reproducibility instructions and limitations.
4. Inspect the code and workflows if deeper technical assurance is required.

---

*Independent portfolio work by Oluwatosin Mulero. Technical details and evidence are maintained in this repository.*
