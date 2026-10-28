#!/usr/bin/env python3
"""Generate 1000 fictitious, varied plain-text CVs for IT consultants working
in business intelligence, data science, and cloud infrastructure.

Run query_generation.py first: the CVs are generated against the search
profiles in queries/. For every profile the corpus contains 1-3 very good
matches, 4-6 reasonable matches and a few near-misses (label rules in
src/evolve_demo/labels.py); the remaining CVs are distractors. Every CV is
labelled against ALL profiles while it is generated, and a CV is only kept if
it matches exactly the profile it was planted for (and no other profile), so
the counts are exact. The existing CVs/ folder is overwritten.
"""
import collections
import glob
import os
import random
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "src"))
from evolve_demo import labels  # noqa: E402

random.seed(42)

N_CVS = 1000
OUT_DIR = os.path.join(SCRIPT_DIR, "CVs")
QUERY_DIR = os.path.join(SCRIPT_DIR, "queries")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------- names ----
FIRST_NAMES = [
    "Anna", "Lukas", "Mia", "Jonas", "Laura", "Felix", "Sophie", "David",
    "Julia", "Maximilian", "Sarah", "Tobias", "Lena", "Michael", "Nora",
    "Daniel", "Hannah", "Simon", "Clara", "Paul", "Emma", "Jan", "Lea",
    "Matthias", "Nina", "Stefan", "Marie", "Philipp", "Charlotte", "Sebastian",
    "Aisha", "Raj", "Priya", "Wei", "Ahmed", "Fatima", "Carlos", "Elena",
    "Marco", "Isabelle", "Erik", "Ingrid", "Liam", "Olivia", "Noah", "Emily",
    "James", "Grace", "Thomas", "Chloe", "Henrik", "Astrid", "Pieter",
    "Femke", "Giulia", "Alessandro", "Katarzyna", "Pawel", "Viktor", "Dmitri",
    "Yuki", "Hiroshi", "Sanjay", "Deepa", "Kwame", "Amara", "Oscar", "Freya",
    "Bjorn", "Sigrid", "Rosa", "Diego", "Camille", "Antoine", "Greta",
    "Klaus", "Petra", "Wolfgang", "Ute", "Dieter", "Christiane",
]
LAST_NAMES = [
    "Muller", "Schmidt", "Fischer", "Weber", "Wagner", "Becker", "Hoffmann",
    "Schafer", "Koch", "Bauer", "Richter", "Klein", "Wolf", "Schroder",
    "Neumann", "Schwarz", "Zimmermann", "Braun", "Kruger", "Hofmann",
    "Sharma", "Patel", "Chen", "Nakamura", "Kowalski", "Nowak", "Ivanov",
    "Petrov", "Andersson", "Johansson", "Jansen", "de Vries", "Rossi",
    "Bianchi", "Garcia", "Martinez", "Lopez", "Dubois", "Moreau", "Lambert",
    "Owusu", "Mensah", "Okafor", "Singh", "Gupta", "Iyer", "Larsen",
    "Nielsen", "Berg", "Lindqvist", "Novak", "Horvat", "Dvorak", "Kovac",
]

# ------------------------------------------------------------ locations ----
LOCATIONS = [
    ("Munich", "Germany"), ("Hamburg", "Germany"), ("Berlin", "Germany"),
    ("Frankfurt", "Germany"), ("Cologne", "Germany"), ("Stuttgart", "Germany"),
    ("Zurich", "Switzerland"), ("Vienna", "Austria"), ("Amsterdam", "Netherlands"),
    ("Rotterdam", "Netherlands"), ("Brussels", "Belgium"), ("Paris", "France"),
    ("Lyon", "France"), ("Milan", "Italy"), ("Warsaw", "Poland"),
    ("Krakow", "Poland"), ("Prague", "Czech Republic"), ("Copenhagen", "Denmark"),
    ("Stockholm", "Sweden"), ("Oslo", "Norway"), ("Helsinki", "Finland"),
    ("Dublin", "Ireland"), ("London", "United Kingdom"), ("Manchester", "United Kingdom"),
    ("Madrid", "Spain"), ("Barcelona", "Spain"), ("Lisbon", "Portugal"),
    ("Bangalore", "India"), ("Pune", "India"), ("Singapore", "Singapore"),
    ("Toronto", "Canada"), ("Chicago", "USA"), ("Austin", "USA"),
]

DEGREES = [
    "B.Sc. in Computer Science", "M.Sc. in Computer Science",
    "M.Sc. in Data Science", "B.Sc. in Business Informatics",
    "M.Sc. in Business Informatics", "M.Sc. in Statistics",
    "B.Eng. in Information Systems", "M.Sc. in Applied Mathematics",
    "MBA with focus on Information Management", "M.Sc. in Software Engineering",
    "B.Sc. in Industrial Engineering", "M.Sc. in Artificial Intelligence",
    "B.Sc. in Mathematics", "M.Sc. in Computational Science",
]
UNIVERSITIES = [
    ("Technical University of Munich", "Munich", "Germany"),
    ("University of Hamburg", "Hamburg", "Germany"),
    ("Humboldt University of Berlin", "Berlin", "Germany"),
    ("ETH Zurich", "Zurich", "Switzerland"),
    ("University of Vienna", "Vienna", "Austria"),
    ("University of Amsterdam", "Amsterdam", "Netherlands"),
    ("Delft University of Technology", "Delft", "Netherlands"),
    ("Sorbonne University", "Paris", "France"),
    ("Politecnico di Milano", "Milan", "Italy"),
    ("University of Warsaw", "Warsaw", "Poland"),
    ("Charles University", "Prague", "Czech Republic"),
    ("Technical University of Denmark", "Copenhagen", "Denmark"),
    ("KTH Royal Institute of Technology", "Stockholm", "Sweden"),
    ("University of Oslo", "Oslo", "Norway"),
    ("Trinity College Dublin", "Dublin", "Ireland"),
    ("Imperial College London", "London", "United Kingdom"),
    ("University of Manchester", "Manchester", "United Kingdom"),
    ("Universidad Politecnica de Madrid", "Madrid", "Spain"),
    ("Indian Institute of Technology Bombay", "Mumbai", "India"),
    ("National University of Singapore", "Singapore", "Singapore"),
    ("University of Toronto", "Toronto", "Canada"),
    ("University of Illinois", "Chicago", "USA"),
]

CERTS = [
    "AWS Certified Solutions Architect - Associate",
    "AWS Certified Data Analytics - Specialty",
    "Microsoft Certified: Azure Data Engineer Associate",
    "Microsoft Certified: Azure Solutions Architect Expert",
    "Microsoft Certified: Power BI Data Analyst Associate",
    "Google Professional Data Engineer",
    "Google Professional Cloud Architect",
    "Certified Kubernetes Administrator (CKA)",
    "HashiCorp Certified: Terraform Associate",
    "Databricks Certified Data Engineer Associate",
    "Databricks Certified Machine Learning Associate",
    "Tableau Desktop Specialist",
    "SnowPro Core Certification",
    "Certified ScrumMaster (CSM)",
    "Project Management Professional (PMP)",
    "TOGAF 9 Certified",
    "Cloudera Certified Data Analyst",
    "Qlik Sense Data Architect Certification",
]

LANGUAGES = [
    "English", "German", "French", "Spanish", "Italian", "Dutch", "Polish",
    "Portuguese", "Mandarin", "Hindi", "Swedish", "Danish",
]

CLIENT_INDUSTRIES = [
    "retail", "banking", "insurance", "automotive manufacturing", "telecommunications",
    "healthcare", "logistics", "energy and utilities", "public sector",
    "pharmaceuticals", "e-commerce", "aviation", "consumer goods",
]

COMPANIES = [
    "Nordwind Consulting", "BlueRiver Analytics", "Kestrel Data Solutions",
    "Silverline IT Consulting", "Meridian Digital Partners", "Alpenglow Analytics",
    "Northgate Technology Group", "Vantage Point Consulting", "Clearwater Data Systems",
    "Ironwood Cloud Services", "Beacon Insight Consulting", "Cobalt Data Labs",
    "Orbis Technology Partners", "Lumen Analytics Group", "Harborview Consulting",
    "Fjord Digital Solutions", "Stratos Cloud Consulting", "Greystone Data & AI",
    "Pinnacle Business Intelligence GmbH", "Quantara Analytics", "Nimbus Infrastructure Consulting",
    "Solaris Data Engineering", "Brightfield Consulting", "Anchor Point Technologies",
    "TerraLogic Consulting", "Vertex Data Partners", "Northstar Cloud Group",
    "Riverbend Analytics", "Falcon Ridge Consulting", "Evergreen Data Solutions",
]

# ------------------------------------------------------------- skills -----
SKILLS_BI = [
    "Power BI", "DAX", "Power Query / M", "Tableau", "QlikView", "Qlik Sense",
    "SSRS", "SSAS", "SSIS", "Looker", "LookML", "Data Warehouse design (Kimball/Inmon)",
    "Star schema & dimensional modeling", "SQL Server", "T-SQL", "Snowflake",
    "dbt", "Stakeholder reporting & dashboarding", "KPI design",
]
SKILLS_DS = [
    "Python (pandas, NumPy, scikit-learn)", "R", "TensorFlow", "PyTorch",
    "Natural Language Processing", "Computer Vision", "Time Series Forecasting",
    "A/B Testing & Experimentation", "Statistical Modeling", "Feature Engineering",
    "MLOps", "MLflow", "Apache Spark / PySpark", "Databricks", "Jupyter",
    "Model Deployment & Monitoring", "XGBoost / LightGBM", "Causal Inference",
]
SKILLS_CLOUD = [
    "AWS (EC2, S3, Lambda, Redshift, Glue)", "Microsoft Azure (Data Factory, Synapse, AKS)",
    "Google Cloud Platform (BigQuery, Dataflow, GKE)", "Terraform", "Kubernetes",
    "Docker", "CI/CD pipelines (GitHub Actions, Azure DevOps, Jenkins)",
    "Infrastructure as Code", "Apache Kafka", "Apache Airflow", "Snowflake on cloud",
    "Cloud cost optimization", "Networking & VPC design", "Linux system administration",
]
SKILLS_GENERAL = [
    "Git", "Agile / Scrum", "Stakeholder management", "Requirements engineering",
    "Data governance", "Data quality management", "Technical documentation",
    "Client workshops & presentations", "JIRA / Confluence",
]

# ---------------------------------------------------------- bullet pools --
BULLETS_BI = [
    "Designed and delivered {n} interactive {tool} dashboards for {industry} clients, reducing manual reporting effort by {pct}%.",
    "Migrated legacy Excel-based reporting to a centralized {tool} platform, cutting report generation time from days to hours.",
    "Built a dimensional data warehouse (star schema) supporting self-service analytics for {n}+ business users.",
    "Optimized {tool} data models and DAX measures, improving dashboard load times by {pct}%.",
    "Led requirements workshops with {industry} stakeholders to translate business questions into KPI-driven reporting solutions.",
    "Developed ETL pipelines feeding the enterprise data warehouse, processing over {n} million records daily.",
    "Introduced a governance framework for report certification, improving trust in shared BI content across {n} departments.",
    "Trained {n} business analysts on {tool} best practices, establishing a center of excellence for self-service BI.",
    "Rebuilt the group-wide financial reporting suite in {tool}, consolidating {n} disparate spreadsheets into a single source of truth.",
    "Standardized KPI definitions across {n} business units, resolving long-standing discrepancies between departmental reports.",
    "Implemented row-level security in {tool}, enabling secure self-service reporting across {n} regional entities.",
    "Automated the monthly reporting cycle for {article} {industry} client, freeing up {n} analyst days per month for higher-value analysis.",
    "Designed executive scorecards in {tool} used by senior leadership to track strategic KPIs across the {industry} business.",
    "Consolidated {n} regional data marts into a single enterprise data warehouse, simplifying cross-market reporting.",
]
BULLETS_DS = [
    "Developed a {model} model to predict {outcome} for {industry} clients, improving prediction accuracy by {pct}%.",
    "Built an NLP pipeline to automatically classify {n}+ incoming customer messages per day, reducing manual triage time by {pct}%.",
    "Deployed machine learning models to production using MLflow and Docker, enabling automated retraining and monitoring.",
    "Led a proof-of-concept on demand forecasting for {article} {industry} client, achieving a {pct}% reduction in forecast error versus the baseline.",
    "Designed and ran A/B tests to evaluate new recommendation algorithms, driving a {pct}% uplift in conversion rate.",
    "Built a churn prediction model on {n}+ customer records, enabling targeted retention campaigns for the {industry} sector.",
    "Implemented a computer vision solution for automated quality inspection, reducing manual inspection effort by {pct}%.",
    "Mentored a team of {n} junior data scientists on feature engineering and model evaluation best practices.",
    "Migrated exploratory analysis workflows from local notebooks to Databricks, enabling collaborative development at scale.",
    "Built a recommendation engine for {article} {industry} client, contributing to a {pct}% increase in average order value.",
    "Developed an anomaly detection system for {industry} operations, flagging issues {pct}% faster than the previous manual process.",
    "Ran a series of causal inference studies to quantify the impact of marketing campaigns on customer retention.",
    "Automated model retraining and validation pipelines, reducing time-to-production for new models by {pct}%.",
    "Presented data science findings to senior stakeholders, translating model outputs into concrete business recommendations.",
]
BULLETS_CLOUD = [
    "Designed and implemented a multi-account AWS landing zone for {article} {industry} client, improving security posture and cost visibility.",
    "Migrated on-premise data infrastructure to Azure, reducing infrastructure costs by {pct}% and improving system uptime.",
    "Built Infrastructure-as-Code templates using Terraform, reducing environment provisioning time from days to minutes.",
    "Containerized {n}+ legacy applications and deployed them to a Kubernetes cluster, improving deployment frequency and reliability.",
    "Designed a CI/CD pipeline that reduced release cycle time by {pct}% for {article} {industry} client's data platform.",
    "Implemented a data lake on {tool}, ingesting and processing over {n} TB of data monthly from {n} source systems.",
    "Led a cloud cost optimization initiative, identifying savings of {pct}% across compute and storage resources.",
    "Set up monitoring and alerting for cloud infrastructure using CloudWatch/Grafana, reducing incident response time by {pct}%.",
    "Architected a serverless event-driven data pipeline processing {n}+ events per second in near real time.",
    "Established a disaster recovery strategy for cloud data infrastructure, reducing recovery time objectives by {pct}%.",
    "Standardized cloud tagging and cost allocation practices for {article} {industry} client, improving budget accountability across {n} teams.",
    "Automated infrastructure provisioning and configuration using Ansible and Terraform, eliminating manual setup steps.",
    "Led the adoption of a self-service data platform on {tool}, onboarding {n}+ internal teams within the first year.",
    "Performed a cloud security audit for {article} {industry} client, remediating {n} critical findings within the first quarter.",
]

SUMMARY_TEMPLATES = [
    "{title} with {years} years of experience delivering {focus} solutions for clients in {industry}. Passionate about turning complex data into actionable business value.",
    "Results-driven {title} with {years} years of hands-on experience in {focus}, known for combining technical depth with strong stakeholder communication.",
    "{title} specializing in {focus}, with {years} years of consulting experience across {industry} and related sectors.",
    "Experienced {title} ({years} years) with a track record of delivering {focus} projects on time and within budget for demanding enterprise clients.",
    "Versatile {title} with {years} years in the field, combining expertise in {focus} to help organizations modernize their data landscape.",
]

ARCHETYPES = [
    {
        "titles": ["Business Intelligence Consultant", "BI Developer", "Senior BI Consultant", "Analytics Consultant"],
        "focus": "business intelligence and enterprise reporting",
        "skill_mix": [(SKILLS_BI, 6), (SKILLS_CLOUD, 2), (SKILLS_GENERAL, 3)],
        "bullets": [(BULLETS_BI, 3)],
        "weight": 3,
    },
    {
        "titles": ["Data Scientist", "Senior Data Scientist", "Machine Learning Engineer", "Applied Data Scientist"],
        "focus": "data science and machine learning",
        "skill_mix": [(SKILLS_DS, 6), (SKILLS_CLOUD, 2), (SKILLS_GENERAL, 3)],
        "bullets": [(BULLETS_DS, 3)],
        "weight": 3,
    },
    {
        "titles": ["Cloud Infrastructure Consultant", "Cloud Solutions Architect", "DevOps Consultant", "Cloud Engineer"],
        "focus": "cloud infrastructure and platform engineering",
        "skill_mix": [(SKILLS_CLOUD, 6), (SKILLS_BI, 1), (SKILLS_GENERAL, 3)],
        "bullets": [(BULLETS_CLOUD, 3)],
        "weight": 3,
    },
    {
        "titles": ["Data Engineer", "Senior Data Engineer", "Analytics Engineer"],
        "focus": "data engineering, ETL pipelines, and cloud data platforms",
        "skill_mix": [(SKILLS_BI, 3), (SKILLS_CLOUD, 4), (SKILLS_GENERAL, 2)],
        "bullets": [(BULLETS_BI, 1), (BULLETS_CLOUD, 2)],
        "weight": 3,
    },
    {
        "titles": ["Data & Analytics Consultant", "Senior Data Platform Consultant", "Lead Data & AI Consultant"],
        "focus": "business intelligence, data science, and cloud data platforms",
        "skill_mix": [(SKILLS_BI, 3), (SKILLS_DS, 3), (SKILLS_CLOUD, 3), (SKILLS_GENERAL, 2)],
        "bullets": [(BULLETS_BI, 1), (BULLETS_DS, 1), (BULLETS_CLOUD, 1)],
        "weight": 2,
    },
]


DOMAIN_LABEL = {
    id(SKILLS_BI): "Business Intelligence",
    id(SKILLS_DS): "Data Science & Machine Learning",
    id(SKILLS_CLOUD): "Cloud & Infrastructure",
    id(SKILLS_GENERAL): "Tools & Ways of Working",
}
POOL_OF = {s: pool for pool in (SKILLS_BI, SKILLS_DS, SKILLS_CLOUD, SKILLS_GENERAL) for s in pool}

TOOLS = ["Power BI", "Tableau", "Qlik Sense", "Looker", "Snowflake", "Databricks"]

# Bullets that evidence one specific skill in the experience section. They let
# a CV show a skill WITHOUT listing it under CORE SKILLS. Each template must be
# recognised by the skill's alias in labels.SKILL_ALIASES (checked below).
BULLET_EVIDENCE = {
    "Power BI": ["Rolled out Power BI workspaces and certified datasets for {n} business units, standardizing self-service reporting.",
                 "Built a Power BI reporting layer on top of the finance data mart, replacing {n} manual spreadsheets."],
    "DAX": ["Optimized complex DAX measures in the sales model, cutting report refresh times by {pct}%."],
    "Tableau": ["Migrated {n} legacy reports to Tableau and trained business users on self-service exploration."],
    "Qlik Sense": ["Developed Qlik Sense apps for operational reporting used by {n}+ plant managers."],
    "Looker": ["Modeled core business entities in Looker so that {n} teams could explore governed metrics on their own."],
    "Snowflake": ["Designed a Snowflake-based reporting layer, reducing query times for key dashboards by {pct}%."],
    "dbt": ["Introduced dbt for transformation and testing, covering {n}+ models in the analytics layer."],
    "SSRS": ["Replaced {n} manual Excel reports with paginated SSRS reports delivered on a schedule."],
    "SSIS": ["Maintained SSIS packages that load {n} source systems into the enterprise data warehouse."],
    "SSAS": ["Built a tabular SSAS model that serves {n} departments with consistent KPIs."],
    "T-SQL": ["Rewrote performance-critical T-SQL stored procedures, reducing nightly batch runtimes by {pct}%."],
    "SQL Server": ["Administered and tuned SQL Server instances hosting the reporting warehouse."],
    "Star schema & dimensional modeling": ["Modeled a star schema for the sales domain, enabling consistent slicing across {n} dimensions."],
    "KPI design": ["Defined and documented {n} KPIs together with business owners as the basis of the new reporting suite."],
    "Python (pandas, NumPy, scikit-learn)": ["Prototyped models in Python with pandas and scikit-learn, handing them over to engineering after validation."],
    "TensorFlow": ["Trained and tuned TensorFlow models for {outcome}, reducing error by {pct}% over the baseline."],
    "PyTorch": ["Implemented a PyTorch model for {outcome} and served it behind an internal API."],
    "Natural Language Processing": ["Applied NLP techniques to classify support tickets, cutting manual triage by {pct}%."],
    "Computer Vision": ["Delivered a computer vision prototype for defect detection on the production line."],
    "Time Series Forecasting": ["Produced weekly demand forecasts with time series models, improving planning accuracy by {pct}%."],
    "A/B Testing & Experimentation": ["Set up A/B tests for new product features and evaluated the results with the product team."],
    "MLOps": ["Established MLOps practices for versioning, deployment and monitoring of {n} models."],
    "MLflow": ["Tracked experiments and registered models with MLflow across {n} data science projects."],
    "Apache Spark / PySpark": ["Ported batch feature pipelines to PySpark, reducing runtimes by {pct}%."],
    "Databricks": ["Moved notebooks and scheduled jobs to Databricks to simplify collaboration."],
    "XGBoost / LightGBM": ["Tuned XGBoost models for {outcome}, improving recall by {pct}%."],
    "Causal Inference": ["Applied causal inference methods to estimate the uplift of pricing changes."],
    "Feature Engineering": ["Invested in feature engineering on transactional data, creating {n}+ predictive features for the scoring model."],
    "Statistical Modeling": ["Built statistical models to explain the drivers of {outcome} and presented them to management."],
    "Jupyter": ["Shared reproducible Jupyter notebooks with the analytics team."],
    "AWS (EC2, S3, Lambda, Redshift, Glue)": ["Operated production workloads on AWS, including S3-based data lakes and Lambda functions."],
    "Microsoft Azure (Data Factory, Synapse, AKS)": ["Built Azure-based data pipelines with orchestrated daily loads from {n} sources."],
    "Google Cloud Platform (BigQuery, Dataflow, GKE)": ["Built analytics workloads on Google Cloud Platform for {n} product teams."],
    "Terraform": ["Managed cloud environments as code with Terraform modules shared across {n} teams."],
    "Kubernetes": ["Operated Kubernetes clusters for data workloads with autoscaling and monitoring."],
    "Docker": ["Packaged data services as Docker images to ensure consistent deployments."],
    "CI/CD pipelines (GitHub Actions, Azure DevOps, Jenkins)": ["Built CI/CD pipelines for data jobs with automated testing and release gates."],
    "Infrastructure as Code": ["Introduced Infrastructure-as-Code to replace manual environment setup for {n} teams."],
    "Apache Kafka": ["Built Kafka-based streaming ingestion for {n} operational systems."],
    "Apache Airflow": ["Orchestrated {n}+ data pipelines with Apache Airflow, including alerting and backfills."],
    "Snowflake on cloud": ["Operated a cloud Snowflake deployment and tuned warehouse sizing to control spend."],
    "Cloud cost optimization": ["Drove cloud cost optimization across {n} accounts through rightsizing and reserved capacity."],
    "Linux system administration": ["Administered Linux servers hosting data services, including patching and hardening."],
    "Networking & VPC design": ["Designed VPC networking, subnets and private endpoints for the data platform."],
    "Git": ["Introduced Git-based workflows with code review for the analytics team."],
    "Agile / Scrum": ["Worked in Scrum teams with two-week sprints and regular client demos."],
    "JIRA / Confluence": ["Managed backlog and documentation in JIRA and Confluence for {n} concurrent workstreams."],
    "Data quality management": ["Implemented automated data quality checks on {n} critical tables."],
    "Data governance": ["Rolled out data governance roles and policies across {n} departments."],
}
for _skill, _templates in BULLET_EVIDENCE.items():
    for _t in _templates:
        assert re.search(labels.SKILL_ALIASES[_skill], _t), (_skill, _t)

CV_LEVELS = {1: "Conversational", 2: "Professional working proficiency", 3: "Fluent", 4: "Native"}


def weighted_choice(items):
    weights = [it["weight"] for it in items]
    return random.choices(items, weights=weights, k=1)[0]


def fill_bullet(template, avoid=frozenset()):
    industry = random.choice(CLIENT_INDUSTRIES)
    article = "an" if industry[0].lower() in "aeiou" else "a"
    # Do not drop tool names into generic bullets that would evidence a skill
    # the CV is supposed to lack.
    tools = [t for t in TOOLS
             if not any(s in labels.SKILL_ALIASES and re.search(labels.SKILL_ALIASES[s], t) for s in avoid)]
    return template.format(
        n=random.choice([2, 3, 5, 8, 10, 15, 20, 30, 50]),
        pct=random.choice([12, 15, 18, 20, 22, 25, 28, 30, 35, 40, 45]),
        industry=industry,
        article=article,
        tool=random.choice(tools or TOOLS),
        model=random.choice(["gradient boosting", "random forest", "deep learning", "logistic regression", "XGBoost"]),
        outcome=random.choice(["customer churn", "demand", "fraud risk", "equipment failure", "customer lifetime value"]),
    )


def make_name(used_names):
    while True:
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if name not in used_names:
            return name


def make_email(name):
    local = name.lower().replace(" ", ".")
    return f"{local}@example.com"


def make_phone():
    return f"+{random.choice([1, 31, 32, 33, 34, 39, 41, 44, 45, 46, 47, 48, 49])} {random.randint(100,999)} {random.randint(1000000,9999999)}"


def build_skills(archetype, forced=(), avoid=frozenset()):
    """CORE SKILLS block. `forced` skills are always listed, `avoid` skills never."""
    forced_by_pool = collections.defaultdict(list)
    for s in forced:
        forced_by_pool[id(POOL_OF[s])].append(s)
    lines = []
    for pool, count in archetype["skill_mix"]:
        picked = forced_by_pool.pop(id(pool), [])
        candidates = [s for s in pool if s not in picked and s not in avoid]
        need = max(0, min(count, len(pool)) - len(picked))
        picked = picked + random.sample(candidates, min(need, len(candidates)))
        random.shuffle(picked)
        lines.append(f"- {DOMAIN_LABEL[id(pool)]}: {', '.join(picked)}")
    for pool_id, picked in forced_by_pool.items():  # pools outside the archetype's mix
        lines.append(f"- {DOMAIN_LABEL[pool_id]}: {', '.join(picked)}")
    return "\n".join(lines)


def build_experience(archetype, years, avoid=frozenset(), evidence=()):
    n_jobs = 2 if years <= 4 else (3 if years <= 9 else 4)
    total_years = years
    jobs = []
    end_year = 2026

    # Pre-shuffle each bullet pool once per CV so bullets are drawn without
    # replacement across ALL jobs (avoids the same sentence repeating in
    # different roles within one resume).
    pool_cycles = {}
    for pool, _ in archetype["bullets"]:
        key = id(pool)
        if key not in pool_cycles:
            shuffled = pool[:]
            random.shuffle(shuffled)
            pool_cycles[key] = shuffled

    def draw_bullets():
        bullets = []
        for pool, count in archetype["bullets"]:
            key = id(pool)
            cycle = pool_cycles[key]
            count = min(count, len(pool))
            picked = []
            for _ in range(count):
                if not cycle:
                    cycle = pool[:]
                    random.shuffle(cycle)
                    pool_cycles[key] = cycle
                picked.append(cycle.pop())
            bullets.extend(fill_bullet(t, avoid) for t in picked)
        random.shuffle(bullets)
        return bullets

    for i in range(n_jobs):
        span = max(1, total_years // n_jobs + random.choice([-1, 0, 0, 1]))
        span = max(1, span)
        start_year = end_year - span
        title = random.choice(archetype["titles"]) if i == 0 else random.choice(
            archetype["titles"] + ["Consultant", "IT Consultant", "Analyst"]
        )
        company = random.choice(COMPANIES)
        city, country = random.choice(LOCATIONS)
        label = "Present" if i == 0 else str(end_year)
        bullets = draw_bullets()
        jobs.append({
            "title": title,
            "company": company,
            "location": f"{city}, {country}",
            "start": start_year,
            "end": label,
            "bullets": bullets,
        })
        end_year = start_year
        if end_year <= 2026 - total_years:
            break

    for skill in evidence:  # skills that appear only in the bullets
        job = random.choice(jobs)
        bullet = fill_bullet(random.choice(BULLET_EVIDENCE[skill]), avoid)
        job["bullets"].insert(random.randrange(len(job["bullets"]) + 1), bullet)
    return jobs


def build_languages(forced, avoid):
    """forced: {language: level rank}. Exactly one language is Native and listed first."""
    chosen = dict(forced)
    free = [l for l in LANGUAGES if l not in chosen and l not in avoid]
    random.shuffle(free)
    if 4 not in chosen.values():
        chosen[free.pop()] = 4
    for _ in range(random.choice([2, 3]) - len(chosen)):
        if free:
            chosen[free.pop()] = random.choice([1, 2, 3])
    native = [l for l, r in chosen.items() if r == 4]
    others = [l for l in chosen if l not in native]
    random.shuffle(others)
    return [f"- {l} ({CV_LEVELS[chosen[l]]})" for l in native + others]


def build_cv(used_names, plan=None):
    """Build one CV. Without a plan it is a plain random CV (distractor); a plan
    (see make_plan) forces or forbids specific skills, certifications,
    languages and a number of years."""
    plan = plan or {}
    archetype = plan.get("archetype") or weighted_choice(ARCHETYPES)
    forced = set(plan.get("core", ()))
    evidence = list(plan.get("bullet", ()))
    avoid = set(plan.get("avoid", ())) | set(evidence)   # bullet-only skills stay out of CORE SKILLS
    name = make_name(used_names)
    years = plan.get("years") or random.choice([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
    title = random.choice(archetype["titles"])
    city, country = random.choice(LOCATIONS)

    summary = random.choice(SUMMARY_TEMPLATES).format(
        title=title, years=years, focus=archetype["focus"],
        industry=random.choice(CLIENT_INDUSTRIES),
    )

    skills_block = build_skills(archetype, forced, avoid)
    jobs = build_experience(archetype, years, avoid - forced, evidence)

    degree = random.choice(DEGREES)
    university, edu_city, edu_country = random.choice(UNIVERSITIES)
    grad_year = 2026 - years - random.choice([0, 1, 2])

    forced_certs = list(plan.get("certs", ()))
    n_certs = max(random.choice([1, 2, 2, 3]), len(forced_certs))
    pool = [c for c in CERTS if c not in forced_certs and c not in plan.get("avoid_certs", ())]
    certs = forced_certs + random.sample(pool, n_certs - len(forced_certs))
    random.shuffle(certs)

    lang_lines = build_languages(plan.get("langs", {}), plan.get("avoid_langs", ()))

    lines = []
    lines.append(name)
    lines.append(f"{city}, {country} | {make_email(name)} | {make_phone()}")
    lines.append("")
    lines.append("PROFESSIONAL SUMMARY")
    lines.append(summary)
    lines.append("")
    lines.append("CORE SKILLS")
    lines.append(skills_block)
    lines.append("")
    lines.append("PROFESSIONAL EXPERIENCE")
    lines.append("")
    for job in jobs:
        lines.append(f"{job['title']} | {job['company']} | {job['location']} | {job['start']} - {job['end']}")
        for b in job["bullets"]:
            lines.append(f"- {b}")
        lines.append("")
    lines.append("EDUCATION")
    lines.append(f"{degree}, {university}, {edu_city}, {edu_country} ({grad_year})")
    lines.append("")
    lines.append("CERTIFICATIONS")
    for c in certs:
        lines.append(f"- {c}")
    lines.append("")
    lines.append("LANGUAGES")
    lines.extend(lang_lines)
    lines.append("")
    return name, "\n".join(lines)


# ----------------------------------------------------------- planting ------
ARCHETYPE_BY_SLUG = {}
for _a in ARCHETYPES:
    ARCHETYPE_BY_SLUG[re.sub(r"[^a-z0-9]+", "_", _a["titles"][0].lower().replace("&", "and")).strip("_")] = _a


def load_queries():
    queries = []
    for path in sorted(glob.glob(os.path.join(QUERY_DIR, "*.txt"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        q = labels.parse_query(open(path, encoding="utf-8").read())
        q["id"] = stem
        q["archetype"] = ARCHETYPE_BY_SLUG[stem.rsplit("_", 1)[0]]
        queries.append(q)
    return queries


def make_plan(q, intent):
    """Plan a CV for profile q. intent: VG (very good), RS (reasonable) or NM
    (near-miss: looks like a fit but fails exactly one hard rule).
    The plan is only a recipe: the labeler decides what the CV really is."""
    must, nice, certs = list(q["must"]), list(q["nice"]), list(q["certs"])
    min_y = q["min_years"]
    exp_years = [y for y in (min_y - 3, min_y - 2) if y >= 2]
    junior_years = [y for y in (min_y - 4, min_y - 5, min_y - 6) if y >= 2]
    lang_below = [n for n, r in q["langs"].items() if r >= 2]

    if intent == "RS":
        options = ["miss1"] + (["exp"] if exp_years else []) + (["lang"] if lang_below else [])
        defects = set(random.sample(options, min(len(options), random.choice([1, 1, 2]))))
    elif intent == "NM":
        options = ["miss2", "nolang", "nonice"] + (["junior"] if junior_years else [])
        defects = {random.choice(options)}
    else:
        defects = set()

    plan = {"archetype": q["archetype"], "core": set(), "bullet": set(), "avoid": set(),
            "certs": [], "avoid_certs": set(), "langs": {}, "avoid_langs": set()}

    def provide(skill):
        # about a third of the skills are shown only in the experience bullets
        if skill in BULLET_EVIDENCE and random.random() < 0.35:
            plan["bullet"].add(skill)
        else:
            plan["core"].add(skill)

    missing = set()
    if "miss1" in defects:
        missing = set(random.sample(must, 1))
    if "miss2" in defects:
        missing = set(random.sample(must, 2))
    for s in must:
        provide(s) if s not in missing else plan["avoid"].add(s)

    if "nonice" in defects:
        plan["avoid"].update(nice)
        plan["avoid_certs"].update(certs)
    else:
        mode = random.choice(["nice", "cert", "both"] if certs else ["nice"])
        if mode in ("nice", "both"):
            for s in random.sample(nice, min(len(nice), random.choice([1, 2]))):
                provide(s)
        if mode in ("cert", "both"):
            plan["certs"] = random.sample(certs, 1)

    if "exp" in defects:
        plan["years"] = random.choice(exp_years)
    elif "junior" in defects:
        plan["years"] = random.choice(junior_years)
    else:
        plan["years"] = random.randint(max(2, min_y - 1), min(15, min_y + 4))

    if "nolang" in defects:
        plan["avoid_langs"] = set(q["langs"])
    elif "lang" in defects:
        lang = random.choice(lang_below)
        plan["langs"][lang] = random.randint(1, q["langs"][lang] - 1)
        plan["avoid_langs"] = set(q["langs"]) - {lang}
    else:
        lang = random.choice(list(q["langs"]))
        plan["langs"][lang] = random.randint(q["langs"][lang], 4)
    return plan


def main():
    queries = load_queries()
    assert len(queries) == 100, "run query_generation.py first"
    intents = []
    for q in queries:
        intents += [(q, "VG")] * random.choice([1, 2, 3])
        intents += [(q, "RS")] * random.choice([4, 5, 6])
        intents += [(q, "NM")] * random.choice([1, 2])
    n_planted = len(intents)
    assert n_planted <= N_CVS, n_planted
    intents += [(None, "DIST")] * (N_CVS - n_planted)
    random.shuffle(intents)

    used_names, accepted, attempts = set(), [], collections.Counter()
    for q, intent in intents:
        while True:
            attempts[intent] += 1
            name, text = build_cv(used_names, make_plan(q, intent) if q else None)
            cv = labels.parse_cv(text)
            hits = {qq["id"]: lab for qq in queries if (lab := labels.label(cv, qq))}
            # strict: a CV matches only the profile it was planted for
            wanted = {q["id"]: 2 if intent == "VG" else 1} if intent in ("VG", "RS") else {}
            if hits == wanted:
                break
        used_names.add(name)
        accepted.append((name, text))
    random.shuffle(accepted)   # file order must not reveal the planting

    for old in glob.glob(os.path.join(OUT_DIR, "CV_*.txt")):
        os.remove(old)
    for i, (name, text) in enumerate(accepted, 1):
        with open(os.path.join(OUT_DIR, f"CV_{i:04d}_{name.replace(' ', '_')}.txt"), "w", encoding="utf-8") as f:
            f.write(text)
    print(f"Generated {len(accepted)} CVs in {OUT_DIR}")
    print(f"planted {n_planted}, distractors {N_CVS - n_planted}; build attempts per intent: {dict(attempts)}")


if __name__ == "__main__":
    main()
