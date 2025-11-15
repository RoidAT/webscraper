import json
import numpy as np
import networkx as nx
from pyvis.network import Network
from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIG
# ============================================================

GRAPH_FILE = "dom_graph.json"
INDEX_FILE = "dom_embeddings.json"
OUTPUT_FILE = "dom_graph_query_visualization.html"
TOP_K = 10  # how many best matches to highlight


# ============================================================
# LOAD GRAPH
# ============================================================

with open(GRAPH_FILE, "r", encoding="utf-8") as f:
    graph_data = json.load(f)

# Explicitly set edges="links" to match nx.node_link_data default
G = nx.node_link_graph(graph_data, edges="links")


# ============================================================
# COLOR MAP
# ============================================================

COLOR_MAP = {
    "Page_File":       "#ffcc00",
    "External_Page":   "#ff9900",
    "PAGE_ROOT":       "#00cccc",   # page DOM roots
    "DOM_Element":     "#66b3ff",
    "Section_Heading": "#009933",
    "Paragraph":       "#3366cc",
    "Data_Link":       "#ff6666",
}

def get_node_color(node):
    t = G.nodes[node].get("type", "")
    return COLOR_MAP.get(t, "#cccccc")


# ============================================================
# NODE LABELS
# (updated to not depend on text_snippet)
# ============================================================

def get_node_label(node):
    data = G.nodes[node]
    t = data.get("type", "")

    if t == "Page_File":
        return "📄 " + data.get("title", node)

    if t == "External_Page":
        # Show hostname or label or URL
        hostname = data.get("hostname")
        url = data.get("url", node)
        label = data.get("label") or hostname or url
        return "🌐 " + label

    if t == "PAGE_ROOT":
        # Show that this is the DOM root for a page
        page = data.get("page", "")
        tag = data.get("tag", "")
        if page:
            return f"🏠 ROOT {page} <{tag}>"
        return f"🏠 ROOT <{tag}>"

    if t == "Paragraph":
        txt = data.get("full_text", "")
        return "P: " + (txt[:40] + "..." if txt else node)

    if t in ["Section_Heading", "Page_Title"]:
        return data.get("heading_text") or data.get("title_text") or node

    if t == "Data_Link":
        return "🔗 " + data.get("value", "")

    # Fallback: generic tag
    return f"<{data.get('tag', '')}> {node}"


# ============================================================
# SIZE: BASE + BOOST FOR MATCHED NODES
# ============================================================

def get_node_size(node, match_scores=None):
    """
    Node size:
    - base size depends a bit on type
    - if node is in match_scores, boost its size proportional to score
    """
    data = G.nodes[node]
    t = data.get("type", "")

    # base sizes per type
    if t == "Page_File":
        base_size = 40
    elif t == "PAGE_ROOT":
        base_size = 35
    elif t == "External_Page":
        base_size = 30
    else:
        base_size = 18  # generic base

    if match_scores and node in match_scores:
        # match_scores[node] is normalized between 0 and 1
        s = match_scores[node]
        # Scale between base_size and a max highlight
        max_size = 80
        size = base_size + s * (max_size - base_size)
        return size

    return base_size


# ============================================================
# LOAD EMBEDDING INDEX
# ============================================================

def load_index(path=INDEX_FILE):
    """Load embeddings, ids, texts, metadata from JSON index."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ids = [d["id"] for d in data]
    texts = [d["text"] for d in data]
    metas = [d["metadata"] for d in data]
    embs = np.array([d["embedding"] for d in data], dtype="float32")

    return ids, texts, metas, embs


# ============================================================
# LOCAL EMBEDDING MODEL (same as in RAG pipeline)
# ============================================================

embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def embed_query(text: str):
    emb = embedding_model.encode(
        [text],
        normalize_embeddings=True,
        show_progress_bar=False
    )
    return emb[0]  # shape (dim,)


# ============================================================
# RAG RETRIEVAL (RE-USE INDEX)
# ============================================================

def find_best_matches(query: str, top_k: int = TOP_K):
    """
    Returns:
      - matches: list of dicts {node_id, score, text, metadata}
      - scores_dict: {node_id -> normalized_score in [0, 1]}
    """
    ids, texts, metas, embs = load_index()

    q_emb = embed_query(query)
    sims = embs @ q_emb  # cosine similarity (embeddings normalized)

    top_indices = np.argsort(-sims)[:top_k]

    # raw scores
    raw_scores = [float(sims[i]) for i in top_indices]
    min_s = min(raw_scores)
    max_s = max(raw_scores)

    # normalize to [0,1] for sizing
    if max_s - min_s < 1e-8:
        norm_scores = [1.0 for _ in raw_scores]
    else:
        norm_scores = [(s - min_s) / (max_s - min_s) for s in raw_scores]

    matches = []
    scores_dict = {}
    for rank, (idx, s, ns) in enumerate(zip(top_indices, raw_scores, norm_scores)):
        node_id = ids[idx]
        matches.append(
            {
                "node_id": node_id,
                "score": s,
                "norm_score": ns,
                "text": texts[idx],
                "metadata": metas[idx],
                "rank": rank + 1,
            }
        )
        scores_dict[node_id] = ns

    return matches, scores_dict


# ============================================================
# BUILD INTERACTIVE VISUALIZATION WITH HIGHLIGHTED MATCHES
# ============================================================

def visualize_query(query: str, top_k: int = TOP_K, output_file: str = OUTPUT_FILE):
    print(f"\nRunning query: {query!r}")
    matches, scores_dict = find_best_matches(query, top_k=top_k)

    print(f"\nTop {len(matches)} matches:")
    for m in matches:
        print(f"\n#{m['rank']}  Node: {m['node_id']}")
        print(f"Score: {m['score']:.4f} (norm: {m['norm_score']:.3f})")
        print("Text snippet:")
        print(m["text"][:400] + ("..." if len(m["text"]) > 400 else ""))
        print("-" * 60)

    print("\nCreating visualization...")

    net = Network(
        height="900px",
        width="100%",
        directed=True,
        notebook=False
    )

    net.barnes_hut(
        gravity=-20000,
        central_gravity=0.2,
        spring_length=170,
        spring_strength=0.01,
        damping=0.95
    )

    # Add nodes
    for node, attrs in G.nodes(data=True):
        net.add_node(
            node,
            label=get_node_label(node),
            color=get_node_color(node),
            title=json.dumps(attrs, indent=2),
            shape="dot",
            size=get_node_size(node, scores_dict),
        )

    # Add edges
    for u, v, attrs in G.edges(data=True):
        rel = attrs.get("relation", "")
        net.add_edge(u, v, title=rel, label=rel)

    net.write_html(output_file)
    print(f"Interactive visualization saved: {output_file}")
    print("Matched nodes are larger; better matches are biggest.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    user_query = input("Enter a query for visualization: ").strip()
    if not user_query:
        print("No query provided, aborting.")
    else:
        visualize_query(user_query, top_k=TOP_K, output_file=OUTPUT_FILE)
