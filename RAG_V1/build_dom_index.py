# build_dom_index.py

import json
import numpy as np
import networkx as nx
from sentence_transformers import SentenceTransformer

GRAPH_FILE = "dom_graph.json"
INDEX_FILE = "dom_embeddings.json"

# ------------------------------------------------------------
# LOAD GRAPH
# ------------------------------------------------------------

with open(GRAPH_FILE, "r", encoding="utf-8") as f:
    graph_data = json.load(f)

G = nx.node_link_graph(graph_data, edges="links")


# ------------------------------------------------------------
# OPTIONAL: TEXT EXTRACTION PER NODE
# ------------------------------------------------------------

def node_to_text(node_id: str, attrs: dict) -> str:
    """
    Build the text that will be embedded for a given node.
    Adjust this to match what you want your RAG to "see".
    """
    t = attrs.get("type", "")
    parts = []

    if t == "Page_File":
        parts.append(attrs.get("title", ""))
        parts.append(attrs.get("path", ""))
    elif t == "External_Page":
        parts.append(attrs.get("label", ""))
        parts.append(attrs.get("hostname", ""))
        parts.append(attrs.get("url", ""))
    elif t == "PAGE_ROOT":
        parts.append(attrs.get("page", ""))
        parts.append(attrs.get("tag", ""))
    elif t == "Paragraph":
        parts.append(attrs.get("full_text", ""))
    elif t in ["Section_Heading", "Page_Title"]:
        parts.append(attrs.get("heading_text") or attrs.get("title_text") or "")
    elif t == "Data_Link":
        parts.append(attrs.get("value", ""))
        parts.append(attrs.get("label", ""))

    # Fallback: all attrs as JSON string if nothing else
    base_text = " ".join(p for p in parts if p)
    if not base_text.strip():
        base_text = json.dumps(attrs, ensure_ascii=False)

    # You can also prepend node id if you want:
    # base_text = f"Node {node_id}: " + base_text

    return base_text


# ------------------------------------------------------------
# BUILD INDEX (EMBEDDINGS)
# ------------------------------------------------------------

print("Collecting node texts...")
node_ids = []
texts = []
metadatas = []

for node_id, attrs in G.nodes(data=True):
    node_ids.append(node_id)
    texts.append(node_to_text(node_id, attrs))
    metadatas.append(attrs)

print(f"Total nodes to embed: {len(node_ids)}")

print("Loading embedding model...")
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

print("Encoding embeddings (this is done only once)...")
embs = embedding_model.encode(
    texts,
    normalize_embeddings=True,
    show_progress_bar=True
)

# Convert to Python lists for JSON
embs = np.asarray(embs, dtype="float32")

index_data = []
for node_id, text, meta, emb in zip(node_ids, texts, metadatas, embs):
    index_data.append(
        {
            "id": node_id,
            "text": text,
            "metadata": meta,
            "embedding": emb.tolist(),
        }
    )

print(f"Saving index to {INDEX_FILE} ...")
with open(INDEX_FILE, "w", encoding="utf-8") as f:
    json.dump(index_data, f, ensure_ascii=False, indent=2)

print("Done. You can now use dom_query_visualization.py without re-embedding the graph.")
