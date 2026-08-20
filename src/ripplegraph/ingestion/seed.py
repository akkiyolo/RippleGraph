"""Pre-built demo memories — instant seeding, no LLM extraction needed.

These memories simulate 5 sessions of a software project where the tech
stack evolves over time, creating supersession chains and temporal history.
"""

from __future__ import annotations

import logging
from datetime import datetime

from ripplegraph.clients.pg_store import PgStore

logger = logging.getLogger(__name__)


DEMO_MEMORIES = [
    # Session 1 — March: Initial setup, choose MongoDB
    {
        "id": "mem-s1-mongodb",
        "type": "DECISION",
        "subject": "project",
        "predicate": "uses_database",
        "object": "MongoDB",
        "text": "The team decided to use MongoDB as the project database because they needed something flexible and schema-less.",
        "session_id": "session-1",
        "valid_from": "2026-03-01T10:00:00",
        "importance": 0.9,
    },
    # Session 2 — March: Choose React/Next.js and AWS
    {
        "id": "mem-s2-react",
        "type": "DECISION",
        "subject": "project",
        "predicate": "uses_frontend_framework",
        "object": "React with Next.js",
        "text": "The frontend team chose React with Next.js for server-side rendering capabilities.",
        "session_id": "session-2",
        "valid_from": "2026-03-05T14:00:00",
        "importance": 0.85,
    },
    {
        "id": "mem-s2-aws",
        "type": "DECISION",
        "subject": "project",
        "predicate": "deployment_platform",
        "object": "AWS ECS",
        "text": "The deployment will be on AWS using ECS (Elastic Container Service).",
        "session_id": "session-2",
        "valid_from": "2026-03-05T14:05:00",
        "importance": 0.8,
    },
    # Session 3 — April: Switch from MongoDB to PostgreSQL
    {
        "id": "mem-s3-postgres",
        "type": "DECISION",
        "subject": "project",
        "predicate": "uses_database",
        "object": "PostgreSQL",
        "text": "The team switched from MongoDB to PostgreSQL due to scaling issues. Relational queries were killing performance, and PostgreSQL handles joins much better.",
        "session_id": "session-3",
        "valid_from": "2026-04-15T09:00:00",
        "importance": 0.95,
    },
    {
        "id": "mem-s3-scaling",
        "type": "EVENT",
        "subject": "project",
        "predicate": "experienced_issue",
        "object": "MongoDB scaling problems",
        "text": "The team ran into scaling issues with MongoDB. Relational queries were killing performance.",
        "session_id": "session-3",
        "valid_from": "2026-04-15T09:00:00",
        "importance": 0.7,
    },
    # Session 4 — April: Add Tailwind, switch to GraphQL
    {
        "id": "mem-s4-tailwind",
        "type": "DECISION",
        "subject": "project",
        "predicate": "uses_css_framework",
        "object": "Tailwind CSS",
        "text": "The team decided to use Tailwind CSS for styling instead of plain CSS.",
        "session_id": "session-4",
        "valid_from": "2026-04-20T11:00:00",
        "importance": 0.7,
    },
    {
        "id": "mem-s4-graphql",
        "type": "DECISION",
        "subject": "project",
        "predicate": "uses_api_style",
        "object": "GraphQL",
        "text": "The team decided the API will use GraphQL instead of REST.",
        "session_id": "session-4",
        "valid_from": "2026-04-20T11:05:00",
        "importance": 0.8,
    },
    # Session 5 — May: Switch from AWS to GCP/K8s
    {
        "id": "mem-s5-gcp",
        "type": "DECISION",
        "subject": "project",
        "predicate": "deployment_platform",
        "object": "Kubernetes on GCP",
        "text": "The team moved deployment from AWS ECS to Kubernetes on GCP. GCP offers better pricing and the team has more K8s experience.",
        "session_id": "session-5",
        "valid_from": "2026-05-10T16:00:00",
        "importance": 0.9,
    },
]


DEMO_RELATIONS = [
    # Database supersession chain
    ("mem-s3-postgres", "mem-s1-mongodb", "SUPERSEDES", "PostgreSQL replaced MongoDB as the project database"),
    ("mem-s1-mongodb", "mem-s3-postgres", "SUPERSEDED_BY", "MongoDB was replaced by PostgreSQL"),
    # Deployment supersession chain
    ("mem-s5-gcp", "mem-s2-aws", "SUPERSEDES", "Kubernetes on GCP replaced AWS ECS"),
    ("mem-s2-aws", "mem-s5-gcp", "SUPERSEDED_BY", "AWS ECS was replaced by Kubernetes on GCP"),
    # Causal links
    ("mem-s3-postgres", "mem-s3-scaling", "CAUSED_BY", "The switch to PostgreSQL was caused by MongoDB scaling issues"),
    ("mem-s3-scaling", "mem-s3-postgres", "LED_TO", "Scaling issues led to the switch to PostgreSQL"),
    # Technology relationships
    ("mem-s2-react", "mem-s4-tailwind", "RELATED_TO", "React frontend uses Tailwind CSS for styling"),
    ("mem-s2-react", "mem-s4-graphql", "RELATED_TO", "React frontend uses GraphQL API"),
]


def seed_demo_data(store: PgStore, user_id: str = "demo-user") -> int:
    """Seed the demo dataset into PostgreSQL. Returns number of memories created."""
    # Clear existing demo data
    store.clear_all(user_id)

    # Insert memories
    for mem in DEMO_MEMORIES:
        valid_from = datetime.fromisoformat(mem["valid_from"]) if mem.get("valid_from") else None

        # Mark superseded memories with valid_to
        valid_to = None
        if mem["id"] == "mem-s1-mongodb":
            valid_to = datetime.fromisoformat("2026-04-15T09:00:00")
        elif mem["id"] == "mem-s2-aws":
            valid_to = datetime.fromisoformat("2026-05-10T16:00:00")

        supersedes_id = None
        if mem["id"] == "mem-s3-postgres":
            supersedes_id = "mem-s1-mongodb"
        elif mem["id"] == "mem-s5-gcp":
            supersedes_id = "mem-s2-aws"

        store.upsert_memory(
            id=mem["id"],
            type=mem["type"],
            subject=mem["subject"],
            predicate=mem["predicate"],
            object=mem.get("object", ""),
            text=mem["text"],
            user_id=user_id,
            session_id=mem["session_id"],
            valid_from=valid_from,
            valid_to=valid_to,
            supersedes_id=supersedes_id,
            importance=mem.get("importance", 0.5),
        )

    # Insert relations
    for source, target, rel_type, context in DEMO_RELATIONS:
        store.add_relation(source, target, rel_type, context)

    count = len(DEMO_MEMORIES)
    logger.info("Seeded %d demo memories with %d relations", count, len(DEMO_RELATIONS))
    return count
