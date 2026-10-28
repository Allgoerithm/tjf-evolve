"""Minimal OpenSearch access (plain HTTP via requests): index the CVs and run
the boolean queries produced by the rewriting prompt."""
import json
import os
import time

import requests

from . import labels

URL = os.environ.get("OPENSEARCH_URL", "http://localhost:9200")
INDEX = os.environ.get("OPENSEARCH_INDEX", "cvs")

# Fields a boolean query is run against. Field prefixes in the query text
# (skills:"Power BI", years_experience:[6 TO *]) are possible as well.
SEARCH_FIELDS = ["title^2", "summary", "skills^2", "experience", "certifications", "languages"]

MAPPING = {
    "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
    "mappings": {
        "properties": {
            "name": {"type": "text"},
            "location": {"type": "text"},
            "title": {"type": "text"},
            "summary": {"type": "text"},
            "skills": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "experience": {"type": "text"},
            "certifications": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "languages": {"type": "text"},
            "years_experience": {"type": "integer"},
        }
    },
}


class QueryError(Exception):
    """The query text was rejected by OpenSearch (e.g. a syntax error)."""


def wait_until_ready(url=URL, timeout=180):
    deadline = time.time() + timeout
    while True:
        try:
            r = requests.get(f"{url}/_cluster/health", params={"wait_for_status": "yellow", "timeout": "5s"}, timeout=10)
            if r.ok and r.json().get("status") in ("yellow", "green"):
                return
        except requests.RequestException:
            pass
        if time.time() > deadline:
            raise TimeoutError(f"OpenSearch at {url} not ready after {timeout}s")
        time.sleep(2)


def cv_document(text):
    """Turn the text of a CV into the fields of the index."""
    sec = labels.sections(text)
    lines = text.splitlines()
    skills = []
    for line in labels.bullets(sec["CORE SKILLS"]):
        skills += labels.split_top_level(line.split(": ", 1)[1])
    experience = [l.strip() for l in sec["PROFESSIONAL EXPERIENCE"].splitlines() if l.strip()]
    return {
        "name": lines[0],
        "location": lines[1].split("|")[0].strip(),
        "title": experience[0].split(" | ")[0],     # most recent role
        "summary": sec["PROFESSIONAL SUMMARY"].strip(),
        "skills": skills,
        "experience": "\n".join(l[2:] if l.startswith("- ") else l for l in experience),
        "certifications": labels.bullets(sec["CERTIFICATIONS"]),
        "languages": labels.bullets(sec["LANGUAGES"]),
        "years_experience": labels.parse_cv(text)["years"],
    }


def recreate_index(url=URL, index=INDEX):
    requests.delete(f"{url}/{index}", timeout=30)
    requests.put(f"{url}/{index}", json=MAPPING, timeout=30).raise_for_status()


def bulk_index(docs, url=URL, index=INDEX):
    """docs: {cv_id: document}. Returns the number of indexed documents."""
    lines = []
    for cv_id, doc in docs.items():
        lines.append('{"index":{"_id":%s}}' % json.dumps(cv_id))
        lines.append(json.dumps(doc))
    r = requests.post(f"{url}/{index}/_bulk", data="\n".join(lines) + "\n",
                      headers={"Content-Type": "application/x-ndjson"}, params={"refresh": "true"}, timeout=120)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(next(i["index"]["error"] for i in body["items"] if "error" in i["index"]))
    return len(body["items"])


def search_boolean(query, size=labels.TOP_K, url=URL, index=INDEX):
    """Run boolean query text (Lucene query_string syntax) and return the ids of
    the top `size` CVs. Raises QueryError if OpenSearch rejects the query."""
    body = {
        "size": size,
        "_source": False,
        "query": {"query_string": {"query": query, "fields": SEARCH_FIELDS, "default_operator": "OR"}},
    }
    r = requests.post(f"{url}/{index}/_search", json=body, timeout=30)
    if r.status_code == 400:
        raise QueryError(r.json().get("error", {}).get("root_cause", [{}])[0].get("reason", r.text))
    r.raise_for_status()
    return [h["_id"] for h in r.json()["hits"]["hits"]]
