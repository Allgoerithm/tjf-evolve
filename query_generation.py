#!/usr/bin/env python3
"""Run this BEFORE CV_generation.py (the CVs are planted against these profiles).

Generate 100 fictitious, varied consultant search profiles (staffing
requests), one per file, into queries/. Uses the same archetypes, skills,
industries, locations, certifications and languages as CV_generation.py so
the vocabulary lines up with the generated CVs.
"""
import glob
import os
import random
import re

import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Import CV_generation.py as a module without re-running its CV generation
# (guarded by `if __name__ == "__main__"` in that file).
CV_GEN_PATH = os.path.join(SCRIPT_DIR, "CV_generation.py")
spec = importlib.util.spec_from_file_location("cv_generation", CV_GEN_PATH)
cv_generation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv_generation)

ARCHETYPES = cv_generation.ARCHETYPES
CLIENT_INDUSTRIES = cv_generation.CLIENT_INDUSTRIES
LOCATIONS = cv_generation.LOCATIONS
CERTS = cv_generation.CERTS
LANGUAGES = cv_generation.LANGUAGES
weighted_choice = cv_generation.weighted_choice

random.seed(7)

OUT_DIR = os.path.join(SCRIPT_DIR, "queries")
os.makedirs(OUT_DIR, exist_ok=True)


def slugify(title):
    s = title.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


# One canonical slug per archetype, derived from its primary title.
ARCHETYPE_SLUGS = {id(a): slugify(a["titles"][0]) for a in ARCHETYPES}

# -------------------------------------------------------- project context --
PROJECT_CONTEXTS = {
    "business_intelligence_consultant": [
        "The client's finance department relies on a patchwork of spreadsheets and needs a consolidated, governed reporting layer built on {tool}.",
        "{Article} {industry} client is rolling out a new group-wide KPI framework and needs someone to translate it into production-grade dashboards.",
        "The existing {tool} environment has grown organically over several years and needs to be re-architected for performance and maintainability.",
        "Leadership wants a self-service analytics capability so business users can build their own reports without IT involvement.",
        "The client is replacing a legacy reporting tool with {tool} and needs support migrating {n}+ existing reports.",
        "A newly merged {industry} organization needs a unified reporting model spanning both legacy entities.",
        "The BI team is understaffed ahead of a major annual planning cycle and needs additional hands-on dashboard development capacity.",
    ],
    "data_scientist": [
        "The client wants to move beyond descriptive reporting and build predictive models for {outcome} in the {industry} sector.",
        "An existing proof-of-concept model needs to be hardened, validated, and prepared for production deployment.",
        "The data science team is exploring NLP use cases on unstructured customer feedback and needs additional modeling expertise.",
        "The client is starting a new initiative around {outcome} prediction and needs someone to define the modeling approach end-to-end.",
        "{Article} {industry} client wants to set up a proper experimentation framework for A/B testing across their digital products.",
        "The current model in production has degraded in accuracy and needs root-cause analysis plus a retraining strategy.",
        "The client wants to establish MLOps practices to make model deployment and monitoring repeatable across teams.",
    ],
    "cloud_infrastructure_consultant": [
        "The client is migrating their on-premise data platform to the cloud and needs hands-on architecture and implementation support.",
        "{Article} {industry} client's infrastructure costs have grown out of control and they need an optimization and governance initiative.",
        "The existing Kubernetes setup is unstable under load and needs a review of configuration, scaling, and observability.",
        "The client wants to introduce Infrastructure-as-Code practices to replace manual, ad-hoc environment provisioning.",
        "A new CI/CD pipeline needs to be designed and rolled out across {n}+ application teams.",
        "The client's security team flagged gaps in their cloud landing zone that need to be remediated before an upcoming audit.",
        "The platform team needs support designing a multi-region disaster recovery strategy for their cloud data infrastructure.",
    ],
    "data_engineer": [
        "The client needs a robust ingestion pipeline built to bring {n}+ source systems into a central data platform.",
        "Existing ETL jobs are fragile and poorly documented; the client needs them re-engineered on a modern orchestration stack.",
        "{Article} {industry} client is building a data lake and needs support designing the ingestion, storage, and transformation layers.",
        "The client wants to move batch pipelines to a near real-time streaming architecture using Kafka.",
        "Data quality issues are undermining trust in downstream reporting and the client needs a data quality framework implemented.",
        "The client is consolidating multiple regional data warehouses into a single enterprise platform.",
        "The analytics engineering team needs support adopting dbt for transformation and testing within their cloud data warehouse.",
    ],
    "data_and_analytics_consultant": [
        "The client wants an end-to-end data platform covering ingestion, warehousing, reporting, and predictive analytics for a new business unit.",
        "{Article} {industry} client is launching a broader data & AI strategy and needs a generalist who can bridge BI, data science, and cloud infrastructure.",
        "The client needs a technical lead who can advise across the full data stack, from cloud architecture to executive dashboards.",
        "An internal data platform program is behind schedule and needs a senior consultant able to unblock issues across multiple workstreams.",
        "The client wants a proof-of-concept combining BI reporting and machine learning insights on a shared cloud data platform.",
        "Following a data platform assessment, the client needs a consultant to help prioritize and execute the resulting roadmap.",
    ],
}

ENGAGEMENT_TYPES = [
    "Project staffing (freelance/contractor)",
    "Permanent hire",
    "Managed service team augmentation",
    "Short-term project engagement",
    "Long-term client secondment",
    "Interim / bridge staffing",
]

REMOTE_POLICIES = [
    "Fully remote",
    "Remote within Europe, occasional on-site visits",
    "Hybrid - 2 days on-site per week",
    "On-site required for the first month, then hybrid",
    "Remote with quarterly on-site workshops",
    "On-site required",
]

START_DATES = [
    "ASAP", "Within 2 weeks", "Within 4 weeks", "Immediately",
    "Flexible, ideally within the next month", "Next quarter",
    "As soon as a suitable candidate is found",
]

DURATIONS = [
    "2 months (short-term)", "3 months, extension likely",
    "6 months", "6 months, extension possible",
    "12 months, potential for permanent placement",
    "Ongoing / open-ended", "9 months with a defined project end date",
]

PROFICIENCY = ["fluent", "business level", "conversational", "native"]


def sample_flat_skills(archetype, k):
    # Draw from each domain pool in proportion to the archetype's own
    # skill_mix weighting (same ratios used to build the CV skills section),
    # so e.g. a Cloud archetype's must-haves are actually cloud skills.
    total_weight = sum(weight for _pool, weight in archetype["skill_mix"])
    picked = []
    for pool, weight in archetype["skill_mix"]:
        share = max(1, round(k * weight / total_weight))
        share = min(share, len(pool))
        picked.extend(random.sample(pool, share))
    random.shuffle(picked)
    return picked[:k] if len(picked) > k else picked


def build_query(index, archetype):
    slug = ARCHETYPE_SLUGS[id(archetype)]
    role_title = random.choice(archetype["titles"])
    engagement = random.choice(ENGAGEMENT_TYPES)
    industry = random.choice(CLIENT_INDUSTRIES)
    min_years = random.choice([2, 3, 4, 5, 6, 7, 8, 10])

    all_skills = sample_flat_skills(archetype, random.choice([6, 7, 8]))
    n_must = random.choice([3, 4, 5])
    n_must = min(n_must, len(all_skills) - 1) if len(all_skills) > 1 else len(all_skills)
    must_have = all_skills[:n_must]
    nice_to_have = all_skills[n_must:]

    n_certs = random.choice([0, 1, 1, 2])
    certs = random.sample(CERTS, n_certs) if n_certs else []

    n_langs = random.choice([1, 2])
    langs = random.sample(LANGUAGES, n_langs)
    lang_lines = [f"- {lang} ({random.choice(PROFICIENCY)})" for lang in langs]

    city, country = random.choice(LOCATIONS)
    remote_policy = random.choice(REMOTE_POLICIES)

    context_template = random.choice(PROJECT_CONTEXTS[slug])
    article = "an" if industry[0].lower() in "aeiou" else "a"
    context = context_template.format(
        tool=random.choice(["Power BI", "Tableau", "Qlik Sense", "Looker", "Snowflake", "Databricks"]),
        industry=industry,
        article=article,
        Article=article.capitalize(),
        n=random.choice([3, 5, 8, 10, 15, 20, 30]),
        outcome=random.choice(["customer churn", "demand", "fraud risk", "equipment failure", "customer lifetime value"]),
    )

    start_date = random.choice(START_DATES)
    duration = random.choice(DURATIONS)

    lines = []
    lines.append(f"SEARCH PROFILE #{index:03d}")
    lines.append(f"Role Needed: {role_title}")
    lines.append(f"Engagement Type: {engagement}")
    lines.append(f"Client Industry: {industry.capitalize()}")
    lines.append(f"Minimum Experience: {min_years}+ years")
    lines.append("")
    lines.append("MUST-HAVE SKILLS")
    for s in must_have:
        lines.append(f"- {s}")
    lines.append("")
    if nice_to_have:
        lines.append("NICE-TO-HAVE SKILLS")
        for s in nice_to_have:
            lines.append(f"- {s}")
        lines.append("")
    if certs:
        lines.append("PREFERRED CERTIFICATIONS")
        for c in certs:
            lines.append(f"- {c}")
        lines.append("")
    lines.append("LANGUAGE REQUIREMENTS")
    lines.extend(lang_lines)
    lines.append("")
    lines.append(f"Location / Remote Policy: {remote_policy} (client site: {city}, {country})")
    lines.append("")
    lines.append("PROJECT CONTEXT")
    lines.append(context)
    lines.append("")
    lines.append(f"Start Date: {start_date}")
    lines.append(f"Duration: {duration}")
    lines.append("")

    text = "\n".join(lines)
    filename = f"{slug}_{index:03d}.txt"
    return filename, text


def main():
    for old in glob.glob(os.path.join(OUT_DIR, "*.txt")):
        os.remove(old)
    for i in range(1, 101):
        archetype = weighted_choice(ARCHETYPES)
        filename, text = build_query(i, archetype)
        with open(os.path.join(OUT_DIR, filename), "w", encoding="utf-8") as f:
            f.write(text)
    print(f"Generated {len(os.listdir(OUT_DIR))} search profiles in {OUT_DIR}")


if __name__ == "__main__":
    main()
