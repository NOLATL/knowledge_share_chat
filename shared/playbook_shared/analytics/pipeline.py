"""End-to-end analytics recompute for Epic 2."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Callable

import networkx as nx
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from playbook_shared.analytics import features, openai_ops, repo
from playbook_shared.analytics.models import FeatureProfile, RespondentProfile


@dataclass(frozen=True)
class GrainComputation:
    """One grain's in-memory clustering result, persisted after the run row exists."""

    grain: str
    entities: list
    feats: list[FeatureProfile]
    embeddings: list[list[float]]
    labels: list[int]
    coords: np.ndarray
    silhouette: float

    @property
    def cluster_count(self) -> int:
        return len(set(self.labels)) if self.labels else 0


@dataclass(frozen=True)
class RecomputeSummary:
    respondents_processed: int
    run_id: str | None
    company_benchmarks_written: int = 0
    function_entities: int = 0
    function_clusters: int = 0
    function_silhouette: float = 0.0
    function_benchmarks_written: int = 0
    company_entities: int = 0
    company_clusters: int = 0
    company_silhouette: float = 0.0


# Minimum companies sharing industry+size before peer percentile is used;
# below this we fall back to the whole-company cohort.
# ponytail: constant; make env if presales wants to tune
PEER_MIN = 3


EmbeddingFn = Callable[[list[str]], list[list[float]]]


def recompute(
    *,
    embedding_fn: EmbeddingFn | None = None,
    enforce_gate: bool = True,
    min_silhouette: float = 0.2,
) -> RecomputeSummary:
    """Cluster + benchmark the cohort at the function and company grain (Fork B).

    Respondent answers only feed in as aggregates: entity profiles per
    (company, function) and per company, plus per-respondent maturity for the
    company rollup. There is no respondent-grain clustering."""
    raw_profiles = repo.load_profiles()
    if not raw_profiles:
        return RecomputeSummary(0, None)
    feature_profiles = [features.build_feature_profile(profile) for profile in raw_profiles]
    embedder = embedding_fn or openai_ops.embed_texts

    fn = _compute_grain("function", embedder)
    co = _compute_grain("company", embedder)
    primary = fn if fn.entities else co
    if (
        enforce_gate
        and len(primary.entities) >= 20
        and (primary.cluster_count < 3 or primary.silhouette < min_silhouette)
    ):
        raise RuntimeError(
            f"analytics gate failed ({primary.grain} grain): "
            f"clusters={primary.cluster_count}, silhouette={primary.silhouette:.3f}"
        )

    run_id = repo.create_cluster_run(
        "umap+hdbscan+kmeans",
        {
            "min_silhouette": min_silhouette,
            "respondents": len(raw_profiles),
            "function_entities": len(fn.entities),
            "company_entities": len(co.entities),
        },
        primary.cluster_count,
        primary.silhouette,
    )
    function_benchmarks = _persist_grain(run_id, fn)
    # Company rollup rows must exist before the company grain stamps its persona.
    company_benchmarks = _write_company_benchmarks(run_id, raw_profiles, feature_profiles)
    _persist_grain(run_id, co)
    return RecomputeSummary(
        respondents_processed=len(raw_profiles),
        run_id=str(run_id),
        company_benchmarks_written=company_benchmarks,
        function_entities=len(fn.entities),
        function_clusters=fn.cluster_count,
        function_silhouette=fn.silhouette,
        function_benchmarks_written=function_benchmarks,
        company_entities=len(co.entities),
        company_clusters=co.cluster_count,
        company_silhouette=co.silhouette,
    )


def _compute_grain(grain: str, embedder: EmbeddingFn) -> GrainComputation:
    """Cluster one entity grain in memory (persisted once the run row exists)."""
    entities = repo.load_entity_profiles(grain)
    if not entities:
        return GrainComputation(grain, [], [], [], [], np.zeros((0, 2)), 0.0)
    feats = [features.build_feature_profile(entity.profile) for entity in entities]
    embeddings = embedder([feat.profile_text for feat in feats])
    labels, coords, silhouette = _cluster(feats, embeddings)
    return GrainComputation(grain, entities, feats, embeddings, labels, coords, silhouette)


def _persist_grain(run_id, comp: GrainComputation) -> int:
    """Write one grain's clusters, entity embeddings/coords, and benchmarks."""
    if not comp.entities:
        return 0
    model = openai_ops.embedding_model()
    for i, entity in enumerate(comp.entities):
        embedding_id = repo.insert_entity_embedding(
            grain=comp.grain,
            entity_key=entity.key,
            run_id=run_id,
            embedding=[float(v) for v in comp.embeddings[i]],
            feature_vector=comp.feats[i].feature_vector,
            model=model,
        )
        repo.update_entity_umap(embedding_id, float(comp.coords[i][0]), float(comp.coords[i][1]))

    communities = _communities(comp.embeddings)
    cluster_ids = _write_clusters(
        run_id,
        [entity.profile for entity in comp.entities],
        comp.feats,
        comp.embeddings,
        comp.labels,
        communities,
        grain=comp.grain,
    )
    if comp.grain == "function":
        return _write_function_benchmarks(run_id, comp.entities, comp.feats, comp.labels, cluster_ids)
    return _write_company_grain_personas(run_id, comp.entities, comp.labels, cluster_ids)


def _write_function_benchmarks(run_id, entities, feats, labels, cluster_ids) -> int:
    """One function_benchmarks row per (company, function). percentile_peer compares
    against the SAME function_key across companies, with cohort fallback."""
    maturities = np.asarray([feat.maturity_score for feat in feats])
    written = 0
    for i, entity in enumerate(entities):
        peer_idx = [j for j, other in enumerate(entities) if other.function_key == entity.function_key]
        peer_vals = maturities[peer_idx]
        fell_back = len(peer_vals) < PEER_MIN
        repo.insert_function_benchmark(
            company_id=entity.company_id,
            function_key=entity.function_key,
            run_id=run_id,
            respondent_count=entity.member_count,
            avg_maturity=float(feats[i].maturity_score),
            percentile_cohort=_percentile(maturities, feats[i].maturity_score),
            percentile_peer=_percentile(maturities if fell_back else peer_vals, feats[i].maturity_score),
            peer_group={
                "function_key": entity.function_key,
                "n": int(len(maturities) if fell_back else len(peer_vals)),
                "fell_back": fell_back,
            },
            cluster_id=cluster_ids.get(labels[i]),
            common_pain_points=_pain_points([entity.profile]),
            common_tech_stack=_tech_stack([entity.profile]),
        )
        written += 1
    return written


def _write_company_grain_personas(run_id, entities, labels, cluster_ids) -> int:
    """Stamp each company's company-grain persona onto its company_benchmarks row."""
    written = 0
    for i, entity in enumerate(entities):
        if entity.company_id:
            repo.set_company_cluster(entity.company_id, run_id, cluster_ids.get(labels[i]))
            written += 1
    return written


def _cluster(
    profiles: list[FeatureProfile],
    embeddings: list[list[float]],
) -> tuple[list[int], np.ndarray, float]:
    matrix = np.asarray(embeddings, dtype=float)
    feature_matrix = np.asarray(features.numeric_matrix(profiles), dtype=float)
    if feature_matrix.size:
        combined = np.hstack([matrix, StandardScaler().fit_transform(feature_matrix)])
    else:
        combined = matrix

    n = len(profiles)
    if n < 3:
        return [0] * n, _coords(combined, n), 0.0

    desired = max(2, min(5, n // 8 or 2))
    try:
        import hdbscan

        raw = hdbscan.HDBSCAN(min_cluster_size=max(4, n // 20), min_samples=2).fit_predict(combined)
        if len({label for label in raw if label >= 0}) >= 2:
            labels = _renumber_noise(raw)
        else:
            labels = KMeans(n_clusters=desired, random_state=42, n_init="auto").fit_predict(combined)
    except Exception:
        labels = KMeans(n_clusters=desired, random_state=42, n_init="auto").fit_predict(combined)

    score = silhouette_score(combined, labels) if len(set(labels)) > 1 and len(set(labels)) < n else 0.0
    return [int(label) for label in labels], _coords(combined, n), float(score)


def _coords(matrix: np.ndarray, n: int) -> np.ndarray:
    if n < 3:
        return np.zeros((n, 2))
    try:
        import umap

        return umap.UMAP(n_components=2, random_state=42, n_neighbors=min(15, n - 1)).fit_transform(matrix)
    except Exception:
        return PCA(n_components=2, random_state=42).fit_transform(matrix)


def _renumber_noise(labels: np.ndarray) -> list[int]:
    positives = sorted({int(label) for label in labels if label >= 0})
    mapping = {label: i for i, label in enumerate(positives)}
    fallback = len(mapping)
    return [mapping.get(int(label), fallback) for label in labels]


def _communities(embeddings: list[list[float]]) -> dict[int, int]:
    n = len(embeddings)
    if n < 3:
        return {i: 0 for i in range(n)}
    neighbors = NearestNeighbors(n_neighbors=min(6, n), metric="cosine").fit(np.asarray(embeddings))
    _, indices = neighbors.kneighbors(np.asarray(embeddings))
    graph = nx.Graph()
    graph.add_nodes_from(range(n))
    for i, row in enumerate(indices):
        for j in row[1:]:
            graph.add_edge(i, int(j))
    communities = nx.algorithms.community.greedy_modularity_communities(graph)
    result: dict[int, int] = {}
    for community_id, members in enumerate(communities):
        for member in members:
            result[int(member)] = community_id
    return result


def _write_clusters(
    run_id,
    raw_profiles: list[RespondentProfile],
    profiles: list[FeatureProfile],
    embeddings: list[list[float]],
    labels: list[int],
    community_ids: dict[int, int],
    grain: str,
) -> dict[int, str]:
    cluster_ids: dict[int, str] = {}
    by_label: dict[int, list[int]] = defaultdict(list)
    for i, label in enumerate(labels):
        by_label[label].append(i)
    for label, idxs in by_label.items():
        centroid = np.asarray([embeddings[i] for i in idxs], dtype=float).mean(axis=0).tolist()
        pain_points = _pain_points([raw_profiles[i] for i in idxs])
        tech_stack = _tech_stack([raw_profiles[i] for i in idxs])
        maturity = float(np.mean([profiles[i].maturity_score for i in idxs]))
        clustered_raw_profiles = [raw_profiles[i] for i in idxs]
        cluster_name = _cluster_name(
            label=label,
            profiles=clustered_raw_profiles,
            tech_stack=tech_stack,
            maturity=maturity,
        )
        summary = _cluster_summary(
            cluster_name=cluster_name,
            profiles=clustered_raw_profiles,
            size=len(idxs),
            maturity=maturity,
            tech_stack=tech_stack,
            pain_points=pain_points,
        )
        # LLM persona pass (Task 8.4) — best-effort; the heuristic name/summary
        # above is the fallback so recompute never fails on a labeling error.
        buying_persona = None
        try:
            persona = openai_ops.label_cluster(
                _persona_prompt(
                    profiles=clustered_raw_profiles,
                    size=len(idxs),
                    maturity=maturity,
                    tech_stack=tech_stack,
                    pain_points=pain_points,
                )
            )
            if persona.get("label") and persona.get("buying_persona") and persona.get("summary"):
                cluster_name = str(persona["label"]).strip()
                buying_persona = str(persona["buying_persona"]).strip()
                summary = str(persona["summary"]).strip()
        except Exception:  # noqa: BLE001 - labeling is best-effort
            pass
        cluster_id = repo.insert_cluster(
            run_id=run_id,
            centroid=centroid,
            label=cluster_name,
            size=len(idxs),
            avg_maturity=maturity,
            common_pain_points=pain_points,
            common_tech_stack=tech_stack,
            summary=summary,
            community_id=Counter(community_ids.get(i, 0) for i in idxs).most_common(1)[0][0],
            buying_persona=buying_persona,
            grain=grain,
        )
        cluster_ids[label] = str(cluster_id)
    return cluster_ids


def _persona_prompt(
    *,
    profiles: list[RespondentProfile],
    size: int,
    maturity: float,
    tech_stack: list[str],
    pain_points: list[dict[str, float | int | str]],
) -> str:
    roles = Counter((p.role or p.answers.get("ctx.role") or "Finance").strip() for p in profiles)
    pains = ", ".join(_slot_label(str(p["slot_key"])) for p in pain_points[:3]) or "finance operations"
    return (
        "Name this cluster of finance/accounting discovery respondents. Return JSON with: "
        '"label" (a short distinct persona name, e.g. "Spreadsheet-bound mid-market controllers"), '
        '"buying_persona" (1-2 sentences: who they are as a buyer, what motivates the purchase, '
        'how they evaluate tools), and "summary" (2-3 sentences describing the cluster). '
        "Describe maturity qualitatively; never quote numeric scores or averages in the text "
        "(the cluster average gets misread as a single member's score). "
        "Facts: "
        f"{size} respondents; dominant roles {dict(roles.most_common(3))}; "
        f"average maturity {maturity:.1f}/5; common tools {tech_stack or ['mixed']}; "
        f"top pains: {pains}."
    )


def _write_company_benchmarks(
    run_id,
    raw_profiles: list[RespondentProfile],
    profiles: list[FeatureProfile],
) -> int:
    """Roll respondent maturity up to one append-only row per company (Task 8.2).

    The company's persona is the company-grain cluster (company_cluster_id,
    stamped by _persist_grain); there is no intracompany respondent-persona mix,
    so cluster_exposure/primary_cluster_id are written empty."""
    by_company: dict[str, list[int]] = defaultdict(list)
    for i, raw in enumerate(raw_profiles):
        if raw.company_id:
            by_company[raw.company_id].append(i)
    if not by_company:
        return 0

    companies: dict[str, dict] = {}
    for company_id, idxs in by_company.items():
        first = raw_profiles[idxs[0]]
        companies[company_id] = {
            "idxs": idxs,
            "avg_maturity": float(np.mean([profiles[i].maturity_score for i in idxs])),
            "industry": first.company_industry,
            "size_band": first.company_size_band,
            "exposure": {},
            "primary_cluster_id": None,
        }

    cohort = np.asarray([c["avg_maturity"] for c in companies.values()])
    written = 0
    for company_id, c in companies.items():
        peers = np.asarray(
            [
                other["avg_maturity"]
                for other in companies.values()
                if _peer_key(other["industry"], other["size_band"]) == _peer_key(c["industry"], c["size_band"])
            ]
        )
        fell_back = len(peers) < PEER_MIN
        repo.insert_company_benchmark(
            company_id=company_id,
            run_id=run_id,
            respondent_count=len(c["idxs"]),
            avg_maturity=c["avg_maturity"],
            percentile_cohort=_percentile(cohort, c["avg_maturity"]),
            percentile_peer=_percentile(cohort if fell_back else peers, c["avg_maturity"]),
            peer_group={
                "industry": c["industry"],
                "size_band": c["size_band"],
                "n": int(len(cohort) if fell_back else len(peers)),
                "fell_back": fell_back,
            },
            primary_cluster_id=c["primary_cluster_id"],
            cluster_exposure=c["exposure"],
            common_pain_points=_pain_points([raw_profiles[i] for i in c["idxs"]]),
            common_tech_stack=_tech_stack([raw_profiles[i] for i in c["idxs"]]),
        )
        written += 1
    return written


def _peer_key(industry: str | None, size_band: str | None) -> tuple[str, str]:
    """Peer matching is case/whitespace-insensitive — intake industry is free text."""
    return ((industry or "").strip().lower(), (size_band or "").strip().lower())


def _percentile(values: np.ndarray, value: float) -> float:
    return float((values <= value).sum() / len(values) * 100.0) if len(values) else 0.0


def _pain_points(profiles: list[RespondentProfile]) -> list[dict[str, float | int | str]]:
    totals: Counter[str] = Counter()
    respondent_counts: Counter[str] = Counter()
    for profile in profiles:
        for slot, score in features.pain_scores(profile).items():
            if score > 0:
                totals[slot] += score
                respondent_counts[slot] += 1
    return [
        {
            "slot_key": key,
            "count": respondent_counts[key],
            "score": round(score, 3),
            "avg_score": round(score / respondent_counts[key], 3),
        }
        for key, score in totals.most_common(3)
    ]


def _tech_stack(profiles: list[RespondentProfile]) -> list[str]:
    text = " ".join(
        " ".join(profile.answers.get(slot, "") for slot in ("sys.erp", "sys.dataprep_tools", "sys.epm_close_tools"))
        for profile in profiles
    ).lower()
    recognized_tools = features.ERPS + features.TOOLS + ("blackline",)
    return [name for name in recognized_tools if name in text][:5]


def _cluster_name(
    *,
    label: int,
    profiles: list[RespondentProfile],
    tech_stack: list[str],
    maturity: float,
) -> str:
    maturity_band = "Advanced" if maturity >= 3.5 else "Manual-heavy" if maturity < 2.5 else "Developing"
    role = _dominant_role(profiles)
    size = _dominant_size(profiles)
    tech = _tech_descriptor(tech_stack)
    return f"{maturity_band} {role} - {size} {tech} group {label + 1}"


def _cluster_summary(
    *,
    cluster_name: str,
    profiles: list[RespondentProfile],
    size: int,
    maturity: float,
    tech_stack: list[str],
    pain_points: list[dict[str, float | int | str]],
) -> str:
    role = _dominant_role(profiles)
    company_size = _dominant_size(profiles)
    tech = ", ".join(tech_stack[:4]) if tech_stack else "mixed finance tooling"
    pains = ", ".join(_slot_label(str(pain["slot_key"])) for pain in pain_points[:3])
    maturity_band = "advanced" if maturity >= 3.5 else "manual-heavy" if maturity < 2.5 else "developing"
    return (
        f"{cluster_name}: {size} respondents with {maturity_band} operations. "
        f"Skews toward {role.lower()} respondents at {company_size.lower()} companies using {tech}. "
        f"Common pressure areas: {pains or 'finance operations'}."
    )


def _dominant_role(profiles: list[RespondentProfile]) -> str:
    counter = Counter((profile.role or profile.answers.get("ctx.role") or "Finance").strip() for profile in profiles)
    role, count = counter.most_common(1)[0]
    if len(counter) > 1 and count / max(len(profiles), 1) < 0.5:
        return "Mixed finance"
    return role


def _dominant_size(profiles: list[RespondentProfile]) -> str:
    counter = Counter(_size_label(profile.answers.get("ctx.company_profile", "")) for profile in profiles)
    size, count = counter.most_common(1)[0]
    if len(counter) > 1 and count / max(len(profiles), 1) < 0.5:
        return "mixed-size"
    return size


def _size_label(text: str) -> str:
    lowered = text.lower()
    if "1000" in lowered or "enterprise" in lowered:
        return "enterprise"
    if "201" in lowered or "mid-market" in lowered:
        return "mid-market"
    if "51" in lowered or "growth" in lowered:
        return "growth"
    if "1-50" in lowered or "fewer than 50" in lowered or "small" in lowered:
        return "small"
    return "mixed-size"


def _tech_descriptor(tech_stack: list[str]) -> str:
    non_excel = [tool for tool in tech_stack if tool != "excel"]
    if not tech_stack:
        return "operations"
    if {"sql", "python"} & set(tech_stack):
        return "analytics stack"
    if "power query" in tech_stack or "alteryx" in tech_stack:
        return "spreadsheet automation"
    if non_excel:
        return f"{non_excel[0]} stack"
    return "spreadsheet operations"


def _slot_label(slot_key: str) -> str:
    return slot_key.replace("pain.", "").replace("_", " ")
