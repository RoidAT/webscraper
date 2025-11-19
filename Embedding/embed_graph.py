import json
import networkx as nx
from sentence_transformers import SentenceTransformer
import numpy as np
import os


GRAPH_FILE = "Scraper/Output_Graph_Json/dom_graph.json"
OUTPUT_EMBEDDINGS = "Embedding/Output_Embeddings/node_embeddings.json"

# model = SentenceTransformer("intfloat/e5-large-v2")   # extrem stark, kostenlos
model = SentenceTransformer("intfloat/e5-small-v2")


def get_context_text(G, node):
    """Generate a rich context description for a graph node."""

    data = G.nodes[node]
    tag = data.get("tag", "")
    ntype = data.get("type", "")
    text = data.get("text_snippet") or ""
    page = data.get("page")
    xpath = data.get("xpath")
    depth = data.get("depth")

    # Parents
    parents = [
        (p, G.nodes[p])
        for p, _, rel in G.in_edges(node, data="relation")
        if rel == "CONTAINS"
    ]

    # Children
    children = [
        (c, G.nodes[c])
        for _, c, rel in G.out_edges(node, data="relation")
        if rel == "CONTAINS"
    ]

    # Outgoing non-DOM relations (links)
    outgoing_links = [
        (v, rel, G.nodes.get(v))
        for _, v, rel in G.out_edges(node, data="relation")
        if rel != "CONTAINS"
    ]

    # Siblings
    siblings = set()
    for p, pdata in parents:
        for _, sib, rel in G.out_edges(p, data="relation"):
            if sib != node and rel == "CONTAINS":
                siblings.add(sib)

    sibling_infos = [(sib, G.nodes[sib]) for sib in siblings]

    # Build context text
    ctx = [
        f"NODE_ID: {node}",
        f"TYPE: {ntype}",
        f"TAG: {tag}",
        f"TEXT: {text}",
        f"PAGE: {page}",
        f"XPATH: {xpath}",
        f"DEPTH: {depth}",
        "",
        "PARENTS:",
    ]

    for pid, pdata in parents:
        ctx.append(f" - {pid} ({pdata.get('tag')}): {pdata.get('text_snippet','')[:80]}")

    ctx.append("")
    ctx.append("CHILDREN:")
    for cid, cdata in children:
        ctx.append(f" - {cid} ({cdata.get('tag')}): {cdata.get('text_snippet','')[:80]}")

    ctx.append("")
    ctx.append("SIBLINGS:")
    for sid, sdata in sibling_infos:
        ctx.append(f" - {sid} ({sdata.get('tag')}): {sdata.get('text_snippet','')[:80]}")

    ctx.append("")
    ctx.append("OUTGOING LINKS:")
    for target, rel, target_data in outgoing_links:
        if target_data:
            ctx.append(f" - {rel} → {target} ({target_data.get('type')})")
        else:
            ctx.append(f" - {rel} → {target}")

    return "\n".join(ctx)