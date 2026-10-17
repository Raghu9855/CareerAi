"""Reproducible ML training script for CareerAI candidate-job compatibility scoring."""

import json
import os
from datetime import UTC, datetime
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from app.ml.features import FeatureExtractor
from app.ml.skill_extractor import SkillExtractor

# Ensure artifacts directory exists
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


# Diverse synthetic seed dataset representing 5 tiers of match quality
SEED_DATA: list[dict[str, Any]] = [
    # Tier 5: High Match (85 - 98)
    {
        "resume": (
            "Senior Backend Engineer with 7 years of Python experience. Built microservices with FastAPI, "
            "SQLAlchemy, and MySQL. Implemented Redis caching, Docker containerization, and AWS ECS deployment "
            "with GitHub Actions CI/CD. Strong experience with REST APIs and system design."
        ),
        "job": (
            "We are seeking a Senior Python Backend Engineer to scale our microservices. Requirements: 5+ years "
            "Python, expertise in FastAPI or Django, MySQL, Redis, Docker, and AWS. Must have experience with "
            "REST API architecture and CI/CD pipelines."
        ),
        "score": 95.0,
    },
    {
        "resume": (
            "DevOps / Platform Engineer specializing in Kubernetes, Docker, Terraform, and AWS. Designed "
            "multi-region infrastructure, configured CI/CD with GitHub Actions, managed Linux clusters, and "
            "enforced cloud security."
        ),
        "job": (
            "Staff DevOps Engineer needed to manage cloud infrastructure on AWS. Strong experience with "
            "Kubernetes, Docker, Terraform, and CI/CD pipelines required. Linux administration and bash scripting "
            "skills mandatory."
        ),
        "score": 93.0,
    },
    {
        "resume": (
            "Machine Learning Engineer experienced in Python, Scikit-Learn, PyTorch, NumPy, and Pandas. "
            "Built end-to-end NLP pipelines, vector search with ChromaDB and Qdrant, and deployed LLM "
            "RAG applications on AWS."
        ),
        "job": (
            "Senior Machine Learning / AI Engineer. Seeking hands-on experience with Python, Scikit-Learn, PyTorch, "
            "and NLP. Experience building RAG pipelines, LLM interfaces, and vector databases (ChromaDB or Qdrant) "
            "is a strong plus."
        ),
        "score": 94.0,
    },
    {
        "resume": (
            "Full Stack Engineer with 4 years building web apps. Expert in TypeScript, React, Next.js, Node.js, HTML, "
            "and CSS. Integrated REST APIs, designed responsive UI components, and worked with PostgreSQL and Redis."
        ),
        "job": (
            "Full Stack Developer. Must have strong skills in React, TypeScript, Next.js, and Node.js. Experience "
            "integrating REST APIs and working with relational databases (PostgreSQL or MySQL) required."
        ),
        "score": 91.0,
    },
    {
        "resume": (
            "Python Developer with 3 years experience. Skilled in FastAPI, SQLite, SQLAlchemy, Docker, Git, and "
            "automated testing with pytest. Built REST APIs and worked in an Agile scrum team."
        ),
        "job": (
            "Mid-level Python Backend Developer. Requirements: 2+ years Python experience, FastAPI or Flask, "
            "REST APIs, Git, Docker, and familiarity with unit testing."
        ),
        "score": 88.0,
    },
    # Tier 4: Strong Match (70 - 84)
    {
        "resume": (
            "Backend Engineer with 5 years experience in Django, Python, PostgreSQL, and Git. Built REST APIs, "
            "managed database migrations, and used Docker for local dev environments."
        ),
        "job": (
            "Senior Python Backend Engineer needed. Requirements: 4+ years Python, FastAPI experience, MySQL, "
            "Redis, AWS, and Docker. Experience with microservices."
        ),
        "score": 76.0,
    },
    {
        "resume": (
            "Data Analyst skilled in Python, SQL, Pandas, NumPy, and data visualization. Built statistical models "
            "and dashboards. Basic familiarity with Machine Learning and Scikit-Learn."
        ),
        "job": (
            "Junior Machine Learning Engineer. Requirements: Python, Pandas, NumPy, Scikit-Learn, and strong SQL. "
            "Experience training models and evaluating data pipelines."
        ),
        "score": 73.0,
    },
    {
        "resume": (
            "Cloud Architect with deep AWS, Linux, Terraform, and Docker experience. Basic knowledge of "
            "Kubernetes and CI/CD."
        ),
        "job": (
            "DevOps Engineer with deep Kubernetes, Docker, Terraform, and AWS experience. Must know GitHub Actions "
            "CI/CD and system design."
        ),
        "score": 78.0,
    },
    {
        "resume": (
            "Frontend Developer skilled in JavaScript, React, HTML, CSS, and Git. Worked on single-page "
            "applications and collaborated with backend teams using REST APIs."
        ),
        "job": (
            "Frontend Engineer. Requirements: TypeScript, React, Next.js, Tailwind CSS, REST APIs, and responsive "
            "design experience."
        ),
        "score": 75.0,
    },
    # Tier 3: Moderate Match (45 - 69)
    {
        "resume": (
            "Junior Python Developer with bootcamp training. Built personal projects in Flask, SQLite, and Git. "
            "Eager to learn Docker, AWS, and enterprise database systems."
        ),
        "job": (
            "Senior Python Backend Engineer. 5+ years experience required with FastAPI, MySQL, Redis, Docker, and "
            "AWS microservices."
        ),
        "score": 48.0,
    },
    {
        "resume": (
            "Java Software Engineer with 4 years experience in Spring Boot, MySQL, and REST APIs. Built enterprise "
            "backend services with Git and Agile methodologies."
        ),
        "job": (
            "Python Backend Engineer. Must have strong proficiency in Python, FastAPI, SQLAlchemy, Redis, and "
            "AWS cloud deployment."
        ),
        "score": 55.0,
    },
    {
        "resume": (
            "Manual QA Tester experienced in test plan design, bug tracking in Jira, Agile ceremonies, and "
            "basic Git. Some exposure to Python automation scripts."
        ),
        "job": (
            "Software Development Engineer in Test (SDET). Requirements: Strong Python, pytest, Docker, CI/CD, "
            "and REST API automation testing."
        ),
        "score": 50.0,
    },
    {
        "resume": (
            "Data Engineer specializing in SQL, Spark, and ETL pipelines. Experience with PostgreSQL and Python "
            "scripts for data processing."
        ),
        "job": (
            "Machine Learning Engineer. Must know PyTorch, Scikit-Learn, LLM fine-tuning, RAG architecture, "
            "and model deployment on AWS."
        ),
        "score": 58.0,
    },
    # Tier 2: Weak Match (25 - 44)
    {
        "resume": (
            "Frontend Intern with HTML, CSS, and basic JavaScript. Built static landing pages and worked with "
            "Figma designs."
        ),
        "job": (
            "Senior DevOps Engineer. 5+ years managing Kubernetes clusters, AWS cloud infrastructure, Terraform, "
            "and Linux administration."
        ),
        "score": 28.0,
    },
    {
        "resume": (
            "Technical Writer with expertise in API documentation, Markdown, Git, and technical communication. "
            "Collaborated with software engineering teams."
        ),
        "job": (
            "Lead Backend Engineer. Requirements: 8+ years experience in Python or Go, distributed systems design, "
            "gRPC, and high-throughput MySQL optimization."
        ),
        "score": 32.0,
    },
    {
        "resume": (
            "Sales Representative and Account Executive with 5 years B2B SaaS sales experience. Excellent "
            "communication, CRM management, and presentation skills."
        ),
        "job": (
            "Full Stack Software Developer. Requirements: React, TypeScript, Node.js, GraphQL, PostgreSQL, and Docker."
        ),
        "score": 22.0,
    },
    # Tier 1: Negative Controls / Irrelevant (5 - 20)
    {
        "resume": (
            "Executive Chef with 10 years experience in fine dining, menu planning, kitchen leadership, inventory "
            "management, and food safety regulations."
        ),
        "job": (
            "Senior Python Backend Engineer. 5+ years Python, FastAPI, Docker, AWS, and MySQL microservices "
            "experience required."
        ),
        "score": 6.0,
    },
    {
        "resume": (
            "Certified Personal Fitness Trainer specializing in strength coaching, nutrition planning, client "
            "motivation, and workout programs."
        ),
        "job": (
            "Principal Machine Learning Scientist. PhD in Computer Science with publications in PyTorch, NLP, "
            "Transformers, and LLM alignment."
        ),
        "score": 5.0,
    },
    {
        "resume": (
            "Real Estate Agent with experience in residential property sales, negotiation, open houses, and "
            "local market market analysis."
        ),
        "job": ("Cloud Infrastructure Engineer. AWS, Kubernetes, Terraform, Docker, and CI/CD pipelines."),
        "score": 8.0,
    },
]

# Expand synthetic pairs by generating domain variations to make dataset robust (100+ training samples)
AUGMENTATION_FACTORS = 6


def generate_augmented_dataset() -> list[dict[str, Any]]:
    """Augment seed data with minor phrasing variations, skill permutations, and noise to create 100+ robust pairs."""
    dataset = list(SEED_DATA)
    rng = np.random.RandomState(42)

    prefixes = [
        "Proven track record as a ",
        "Experienced professional working as ",
        "Passionate practitioner operating as ",
        "Results-oriented professional: ",
    ]
    suffixes = [
        " Committed to continuous learning and best practices.",
        " Strong problem solver and team collaborator.",
        " Focus on high quality code and reliability.",
        " Looking for high-impact technical challenges.",
    ]

    for item in SEED_DATA:
        base_score = float(item["score"])
        for _ in range(AUGMENTATION_FACTORS):
            prefix = rng.choice(prefixes)
            suffix = rng.choice(suffixes)
            noise = float(rng.normal(0.0, 2.5))
            aug_score = max(5.0, min(99.0, base_score + noise))

            aug_resume = f"{prefix}{item['resume']}{suffix}"
            dataset.append(
                {
                    "resume": aug_resume,
                    "job": item["job"],
                    "score": round(aug_score, 1),
                }
            )

    return dataset


def train_model() -> dict[str, Any]:
    """Train, evaluate, and save CareerAI compatibility scoring model."""
    print("=" * 60)
    print("CareerAI ML Model Training Pipeline")
    print("=" * 60)

    dataset = generate_augmented_dataset()
    print(f"Total dataset size: {len(dataset)} samples")

    # 1. Fit TF-IDF Vectorizer across combined corpus
    all_texts = [d["resume"] for d in dataset] + [d["job"] for d in dataset]
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=1500,
        sublinear_tf=True,
        stop_words="english",
    )
    vectorizer.fit(all_texts)
    print("Fitted TfidfVectorizer with 1500 max features.")

    # 2. Extract features using FeatureExtractor
    extractor = FeatureExtractor(vectorizer=vectorizer, skill_extractor=SkillExtractor())
    X_list = []
    y_list = []

    for d in dataset:
        feats, _ = extractor.extract_features(d["resume"], d["job"])
        X_list.append(feats)
        y_list.append(d["score"])

    X = np.array(X_list, dtype=np.float64)
    y = np.array(y_list, dtype=np.float64)

    # 3. Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"Train samples: {len(X_train)}, Test samples: {len(X_test)}")

    # 4. Train RandomForestRegressor
    regressor = RandomForestRegressor(
        n_estimators=100,
        max_depth=6,
        min_samples_split=3,
        random_state=42,
    )
    regressor.fit(X_train, y_train)

    # 5. Evaluate
    y_pred = regressor.predict(X_test)
    r2 = float(r2_score(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))

    print(f"Holdout Test R² Score : {r2:.4f}")
    print(f"Holdout Test RMSE     : {rmse:.4f}")
    print(f"Holdout Test MAE      : {mae:.4f}")

    # 6. Save model bundle artifact
    artifact_bundle = {
        "regressor": regressor,
        "vectorizer": vectorizer,
        "feature_names": FeatureExtractor.FEATURE_NAMES,
    }
    model_path = os.path.join(ARTIFACTS_DIR, "model.joblib")
    joblib.dump(artifact_bundle, model_path)
    print(f"Saved model artifact to: {model_path}")

    # 7. Write metadata.json
    metadata = {
        "model_name": "RandomForestRegressor",
        "model_version": "v1.0.0-rf-compatibility",
        "trained_at": datetime.now(UTC).isoformat(),
        "dataset_samples": len(dataset),
        "features": FeatureExtractor.FEATURE_NAMES,
        "metrics": {
            "test_r2": round(r2, 4),
            "test_rmse": round(rmse, 4),
            "test_mae": round(mae, 4),
        },
        "hyperparameters": {
            "n_estimators": 100,
            "max_depth": 6,
            "min_samples_split": 3,
            "random_state": 42,
        },
        "limitations": [
            "TF-IDF similarity and keyword matching can miss deep semantic equivalents not in vocabulary",
            "Trained predominantly on technical, software, and professional resume/job descriptions in English",
            "Does not evaluate interpersonal soft skills, cultural match, or verified work samples",
        ],
    }

    metadata_path = os.path.join(ARTIFACTS_DIR, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved model metadata to: {metadata_path}")
    print("=" * 60)

    return metadata


if __name__ == "__main__":
    train_model()
