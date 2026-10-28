"""Rule-based relevance labels for (search profile, CV) pairs.

Every CV gets one of three labels per search profile:

  2  very good fit
       - covers ALL must-have skills
       - has at least (minimum experience - 1) years
       - meets the required level in at least one required language
       - covers at least one nice-to-have skill or one preferred certification
  1  reasonable fit
       - misses at most ONE must-have skill
       - has at least (minimum experience - 3) years
       - has at least one required language (any level)
       - covers at least one nice-to-have skill or one preferred certification
  0  everything else

A skill counts as covered if it is listed in the CORE SKILLS section or, for
skills with an alias below, mentioned in the PROFESSIONAL EXPERIENCE bullets.

Score of a ranked list: sum of the labels of the top TOP_K results, divided by
MAX_SCORE = 2 * TOP_K = 10, the theoretical maximum (TOP_K very good fits). The
best score actually reachable for a profile is usually lower and deliberately
not used as divisor: in practice it is not known either.
"""
import re

TOP_K = 5
MAX_SCORE = 2 * TOP_K   # theoretical maximum: TOP_K very good fits

# Language levels on one ladder. CV levels and profile levels share it
# ("business level" in a profile corresponds to "Professional working
# proficiency" in a CV).
LEVEL_RANK = {
    "conversational": 1,
    "professional working proficiency": 2,
    "business level": 2,
    "fluent": 3,
    "native": 4,
}

# Free-text evidence for a skill in the experience bullets. Skills without an
# entry can only be evidenced through the CORE SKILLS list.
SKILL_ALIASES = {
    # Business Intelligence
    "Power BI": r"\bPower BI\b",
    "DAX": r"\bDAX\b",
    "Tableau": r"\bTableau\b",
    "Qlik Sense": r"\bQlik Sense\b",
    "Looker": r"\bLooker\b",
    "Snowflake": r"\bSnowflake\b",
    "dbt": r"\bdbt\b",
    "SSRS": r"\bSSRS\b",
    "SSIS": r"\bSSIS\b",
    "SSAS": r"\bSSAS\b",
    "T-SQL": r"\bT-SQL\b",
    "SQL Server": r"\bSQL Server\b",
    "Star schema & dimensional modeling": r"(?i)star schema|dimensional model",
    "KPI design": r"\bKPI",
    # Data science
    "Python (pandas, NumPy, scikit-learn)": r"\bPython\b",
    "TensorFlow": r"\bTensorFlow\b",
    "PyTorch": r"\bPyTorch\b",
    "Natural Language Processing": r"\bNLP\b|Natural Language Processing",
    "Computer Vision": r"(?i)computer vision",
    "Time Series Forecasting": r"(?i)time series|forecast",
    "A/B Testing & Experimentation": r"(?i)A/B test",
    "MLOps": r"\bMLOps\b",
    "MLflow": r"\bMLflow\b",
    "Apache Spark / PySpark": r"(?i)spark",
    "Databricks": r"\bDatabricks\b",
    "XGBoost / LightGBM": r"XGBoost|LightGBM",
    "Causal Inference": r"(?i)causal inference",
    "Feature Engineering": r"(?i)feature engineering",
    "Statistical Modeling": r"(?i)statistical model",
    "Jupyter": r"\bJupyter\b",
    # Cloud
    "AWS (EC2, S3, Lambda, Redshift, Glue)": r"\bAWS\b",
    "Microsoft Azure (Data Factory, Synapse, AKS)": r"\bAzure\b",
    "Google Cloud Platform (BigQuery, Dataflow, GKE)": r"(?i)google cloud|\bGCP\b|BigQuery",
    "Terraform": r"\bTerraform\b",
    "Kubernetes": r"\bKubernetes\b",
    "Docker": r"\bDocker\b",
    "CI/CD pipelines (GitHub Actions, Azure DevOps, Jenkins)": r"CI/CD",
    "Infrastructure as Code": r"(?i)infrastructure[- ]as[- ]code",
    "Apache Kafka": r"(?i)kafka",
    "Apache Airflow": r"(?i)airflow",
    "Snowflake on cloud": r"\bSnowflake\b",
    "Cloud cost optimization": r"(?i)cost optimi[sz]ation",
    "Linux system administration": r"(?i)\blinux\b",
    "Networking & VPC design": r"\bVPC\b",
    # General
    "Git": r"\bGit\b",
    "Agile / Scrum": r"(?i)scrum|agile",
    "JIRA / Confluence": r"JIRA|Confluence",
    "Data quality management": r"(?i)data quality",
    "Data governance": r"(?i)data governance",
}
_ALIAS_RE = {skill: re.compile(rx) for skill, rx in SKILL_ALIASES.items()}

_HEADING = re.compile(r"^[A-Z][A-Z &\-]+$")


def sections(text):
    """Split a CV or search profile into {HEADING: body}; the part before the
    first heading is stored under ''."""
    sections, current, lines = {}, "", []
    for line in text.splitlines():
        if _HEADING.match(line.strip()):
            sections[current] = "\n".join(lines)
            current, lines = line.strip(), []
        else:
            lines.append(line)
    sections[current] = "\n".join(lines)
    return sections


def bullets(body):
    return [l[2:].strip() for l in body.splitlines() if l.startswith("- ")]


def split_top_level(s):
    """Split on commas that are not inside parentheses."""
    return [p.strip() for p in re.split(r",\s*(?![^()]*\))", s) if p.strip()]


def _level_rank(name):
    return LEVEL_RANK[name.strip().lower()]


def parse_cv(text):
    sec = sections(text)
    core = set()
    for line in bullets(sec["CORE SKILLS"]):
        core.update(split_top_level(line.split(": ", 1)[1]))
    langs = {}
    for line in bullets(sec["LANGUAGES"]):
        m = re.match(r"(.*) \((.*)\)$", line)
        langs[m.group(1)] = _level_rank(m.group(2))
    return {
        "years": int(re.search(r"(\d+) years", sec["PROFESSIONAL SUMMARY"]).group(1)),
        "core_skills": core,
        "experience": sec["PROFESSIONAL EXPERIENCE"],
        "certs": set(bullets(sec["CERTIFICATIONS"])),
        "langs": langs,
    }


def parse_query(text):
    sec = sections(text)
    head = sec[""]
    langs = {}
    for line in bullets(sec["LANGUAGE REQUIREMENTS"]):
        m = re.match(r"(.*) \((.*)\)$", line)
        langs[m.group(1)] = _level_rank(m.group(2))
    return {
        "min_years": int(re.search(r"Minimum Experience: (\d+)\+ years", head).group(1)),
        "must": bullets(sec["MUST-HAVE SKILLS"]),
        "nice": bullets(sec.get("NICE-TO-HAVE SKILLS", "")),
        "certs": bullets(sec.get("PREFERRED CERTIFICATIONS", "")),
        "langs": langs,
    }


def has_skill(cv, skill):
    if skill in cv["core_skills"]:
        return True
    rx = _ALIAS_RE.get(skill)
    return bool(rx and rx.search(cv["experience"]))


def check(cv, query):
    """The individual facts the label rules are built from."""
    return {
        "missing_must": [s for s in query["must"] if not has_skill(cv, s)],
        "years_gap": cv["years"] - query["min_years"],
        "language_level_met": any(cv["langs"].get(n, 0) >= r for n, r in query["langs"].items()),
        "language_present": any(n in cv["langs"] for n in query["langs"]),
        "nice_or_cert": any(has_skill(cv, s) for s in query["nice"])
        or any(c in cv["certs"] for c in query["certs"]),
    }


def label(cv, query):
    c = check(cv, query)
    if not c["missing_must"] and c["years_gap"] >= -1 and c["language_level_met"] and c["nice_or_cert"]:
        return 2
    if len(c["missing_must"]) <= 1 and c["years_gap"] >= -3 and c["language_present"] and c["nice_or_cert"]:
        return 1
    return 0


def ceiling(labels):
    """Diagnostic only: the best score reachable for a profile (0..1), i.e. the
    TOP_K highest labels over MAX_SCORE. Not used for scoring."""
    return sum(sorted(labels.values(), reverse=True)[:TOP_K]) / MAX_SCORE


def score(ranked_ids, labels):
    """Score (0..1) of a ranked result list: points of the first TOP_K results
    divided by MAX_SCORE."""
    return sum(labels.get(cv_id, 0) for cv_id in ranked_ids[:TOP_K]) / MAX_SCORE
