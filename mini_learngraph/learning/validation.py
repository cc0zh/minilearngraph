"""Full-graph guards shared by submitted refs, model refs and persisted IDs."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from .schemas import Issue


def _data(value: BaseModel | Mapping[str, Any]) -> Mapping[str, Any]:
    return value.model_dump() if isinstance(value, BaseModel) else value


def _reachable(start: str, adjacency: Mapping[str, list[str]]) -> set[str]:
    found: set[str] = set()
    pending = [start]
    while pending:
        current = pending.pop()
        if current not in found:
            found.add(current)
            pending.extend(adjacency.get(current, []))
    return found


def validate_graph(
    nodes: Sequence[BaseModel | Mapping[str, Any]],
    edges: Sequence[BaseModel | Mapping[str, Any]],
    scope: str = "body",
) -> list[Issue]:
    """Collect every determinable structural defect, without mutating the graph.

    Input schemas handle field types and bounds before this guard. Temporary refs
    take precedence over IDs, so edit errors highlight the submitted graph. SCCs
    are identified on the *union* of contains and prerequisite, not separately.
    """
    node_data = [_data(node) for node in nodes]
    edge_data = [_data(edge) for edge in edges]
    identities: list[str] = [node.get("ref", node.get("id")) for node in node_data]
    known = set(identities)
    issues: list[Issue] = []

    def add(
        path: list[str | int], code: str, message: str,
        node_ids: list[str] | None = None, edge_indexes: list[int] | None = None,
    ) -> None:
        issues.append(Issue(
            path=[scope, *path], code=code, message=message,
            node_ids=list(dict.fromkeys(node_ids or [])),
            edge_indexes=sorted(set(edge_indexes or [])),
        ))

    if len(nodes) < 2:
        add(["nodes"], "min_nodes", "A graph requires at least two nodes.", identities)
    if len(nodes) > 100:
        add(["nodes"], "constraint", "A graph allows at most 100 nodes.", identities)
    if len(edges) > 500:
        add(["edges"], "constraint", "A graph allows at most 500 edges.")
    roots = [identity for identity, node in zip(identities, node_data) if node["node_type"] == "root"]
    if len(roots) != 1:
        add(["nodes"], "root_count", "A graph requires exactly one root.", roots)

    seen_refs: dict[str, int] = {}
    seen_ids: dict[str, int] = {}
    for index, (identity, node) in enumerate(zip(identities, node_data)):
        if identity in seen_refs:
            add(["nodes", index, "ref" if "ref" in node else "id"], "duplicate_node",
                "Node identities must be unique.", [identity])
        seen_refs[identity] = index
        existing_id = node.get("id")
        if "ref" in node and existing_id is not None:
            if existing_id in seen_ids:
                first = seen_ids[existing_id]
                add(["nodes", index, "id"], "duplicate_node", "Existing node IDs must be unique.",
                    [identities[first], identity, existing_id])
            seen_ids[existing_id] = index

    incoming: dict[str, list[int]] = defaultdict(list)
    contains: dict[str, list[str]] = defaultdict(list)
    structural: dict[str, list[str]] = defaultdict(list)
    reverse: dict[str, list[str]] = defaultdict(list)
    valid_edges: list[tuple[int, str, str, str]] = []
    seen_edges: dict[tuple[str, str, str], int] = {}
    for index, edge in enumerate(edge_data):
        source_key = "source_ref" if "source_ref" in edge else "source"
        target_key = "target_ref" if "target_ref" in edge else "target"
        source, target, relation = edge[source_key], edge[target_key], edge["relation"]
        triple = source, target, relation
        for key, endpoint in ((source_key, source), (target_key, target)):
            if endpoint not in known:
                add(["edges", index, key], "unknown_endpoint", "An edge endpoint is not in this graph.",
                    [endpoint], [index])
        if triple in seen_edges:
            add(["edges", index], "duplicate_edge", "Edge triples must be unique.",
                [source, target], [seen_edges[triple], index])
        else:
            seen_edges[triple] = index
        if source == target:
            add(["edges", index], "self_loop", "Self loops are not allowed.", [source], [index])
        if relation == "contains" and target in known:
            # An unknown parent still makes a root's incoming edge invalid and
            # can establish a multiple-parent defect on a known child.
            incoming[target].append(index)
        if source not in known or target not in known:
            continue
        valid_edges.append((index, source, target, relation))
        if relation == "contains":
            contains[source].append(target)
        if relation in {"contains", "prerequisite"}:
            structural[source].append(target)
            reverse[target].append(source)

    for index, (identity, node) in enumerate(zip(identities, node_data)):
        parents = incoming[identity]
        parent_nodes = [edge_data[i].get("source_ref", edge_data[i].get("source")) for i in parents]
        if node["node_type"] == "root":
            if parents:
                add(["nodes", index], "root_has_parent", "The root cannot have a contains parent.",
                    [identity, *parent_nodes], parents)
        elif len(parents) != 1:
            add(["nodes", index], "contains_parent_count", "Every non-root needs exactly one contains parent.",
                [identity, *parent_nodes], parents)

    if len(roots) == 1:
        reached = _reachable(roots[0], contains)
        missing = list(dict.fromkeys(identity for identity in identities if identity not in reached))
        if missing:
            indexes = [i for i, source, target, relation in valid_edges
                       if relation == "contains" and (source in missing or target in missing)]
            add(["nodes"], "unreachable", "All nodes must be reachable from the root via contains.", missing, indexes)

    # A forward/reverse reachability intersection is exactly one SCC. This is
    # bounded by the contract's 100 nodes and avoids recursion-depth hazards.
    unchecked = set(identities)
    for identity in dict.fromkeys(identities):
        if identity not in unchecked:
            continue
        component = _reachable(identity, structural) & _reachable(identity, reverse)
        unchecked.difference_update(component)
        indexes = [i for i, source, target, relation in valid_edges
                   if relation in {"contains", "prerequisite"} and source in component and target in component]
        if len(component) > 1 or (len(component) == 1 and indexes):
            members = list(dict.fromkeys(node_id for node_id in identities if node_id in component))
            add(["edges"], "structural_cycle", "Contains and prerequisite must form a directed acyclic graph.",
                members, indexes)
    return issues
