import json
import networkx as nx
from sentence_transformers import SentenceTransformer
import numpy as np


GRAPH_FILE = "dom_graph.json"

with open(GRAPH_FILE, "r", encoding="utf-8") as f:
    graph_data = json.load(f)

G = nx.node_link_graph(graph_data, edges="links")


# ============================================================
# HELPERS
# ============================================================

LINK_RELATIONS = {"LINKS_TO_PAGE", "LINKS_TO_EXTERNAL_PAGE"}


def node_has_link_edges(node):
    """Return True if node participates in any link relation."""
    for _, _, data in G.out_edges(node, data=True):
        if data.get("relation") in LINK_RELATIONS:
            return True
    for _, _, data in G.in_edges(node, data=True):
        if data.get("relation") in LINK_RELATIONS:
            return True
    return False


def should_embed(node, attrs):
    """Your selection logic for embedding candidates."""
    t = attrs.get("type", "")

    if t in ("Page_File", "External_Page"):
        return False

    if t == "DOM_Element":
        # only embed DOM elements that have link connections
        return node_has_link_edges(node)

    # Everything else (Paragraph, Section_Heading, Page_Title, Data_Link, PAGE_ROOT, ...)
    return True


def get_page_name_from_node_id(node_id):
    """
    Your node ids look like: "<page_name>_<tag>_<idx>"
    So we can infer the page name from the prefix.
    """
    return node_id.split("_", 1)[0]


def get_page_file_node(page_name):
    """Return the Page_File node for this page_name (if any)."""
    if page_name in G.nodes and G.nodes[page_name].get("type") == "Page_File":
        return page_name
    # fallback: search by attribute
    for n, data in G.nodes(data=True):
        if data.get("type") == "Page_File" and data.get("title") == page_name:
            return n
    return None


def get_heading_context(node):
    """Climb up the CONTAINS edges to collect heading ancestors."""
    headings = []
    current = node
    visited = set()

    while True:
        preds = [
            u for u, v, d in G.in_edges(current, data=True)
            if d.get("relation") == "CONTAINS"
        ]
        if not preds:
            break

        parent = preds[0]  # tree-like, so at most one
        if parent in visited:
            break
        visited.add(parent)

        pdata = G.nodes[parent]
        if pdata.get("type") == "Section_Heading":
            txt = pdata.get("heading_text") or ""
            if txt:
                level = pdata.get("tag", "h?")
                headings.append(f"{level}: {txt}")
        current = parent

    headings.reverse()  # outermost → innermost
    return headings


def get_link_context(node):
    """Describe outgoing links (to pages or external pages) from this node."""
    ctx_lines = []
    for _, v, data in G.out_edges(node, data=True):
        rel = data.get("relation")
        anchor = data.get("anchor", "")

        if rel == "LINKS_TO_PAGE":
            # v is a Page_File node (filename)
            target_title = G.nodes[v].get("title", v)
            ctx_lines.append(
                f"- link to page '{target_title}' (file: {v}), anchor text: '{anchor}'"
            )

        elif rel == "LINKS_TO_EXTERNAL_PAGE":
            tdata = G.nodes[v]
            url = tdata.get("url", v)
            hostname = tdata.get("hostname", "")
            label = tdata.get("label") or hostname or url
            ctx_lines.append(
                f"- link to external page '{label}' ({url}), anchor text: '{anchor}'"
            )

    return ctx_lines


def build_node_text(node, attrs):
    """Construct a RAG-friendly text block for this node, with context."""
    node_type = attrs.get("type", "")
    tag = attrs.get("tag", "")
    page_name = get_page_name_from_node_id(node)
    page_file_node = get_page_file_node(page_name)

    # --------- Page / file context ---------
    page_title = None
    if page_file_node:
        page_title = G.nodes[page_file_node].get("title", page_file_node)

    header_lines = []
    if page_title:
        header_lines.append(f"Page: {page_title} (file: {page_file_node})")
    else:
        header_lines.append(f"Page ID: {page_name}")

    header_lines.append(f"Node ID: {node}")
    if tag:
        header_lines.append(f"DOM tag: <{tag}>")
    header_lines.append(f"Node type: {node_type}")

    # --------- Heading / structural context ---------
    headings = get_heading_context(node)
    if headings:
        header_lines.append("Heading hierarchy:")
        for h in headings:
            header_lines.append(f"  - {h}")

    # --------- Main content ---------
    main_text = ""
    if node_type == "Paragraph":
        main_text = attrs.get("full_text", "")
    elif node_type in ("Section_Heading", "Page_Title"):
        main_text = attrs.get("heading_text") or attrs.get("title_text", "")
    elif node_type == "Data_Link":
        val = attrs.get("value", "")
        main_text = f"Data link: {val}"
    elif node_type == "PAGE_ROOT":
        main_text = "Root DOM node for this page."
    elif node_type == "DOM_Element":
        # only special DOM elements (with links) reach here
        main_text = "DOM element containing important links."

    # --------- Link context ---------
    link_lines = get_link_context(node)
    if link_lines:
        header_lines.append("Outgoing links:")
        header_lines.extend(link_lines)

    text_parts = [
        "\n".join(header_lines),
    ]
    if main_text:
        text_parts.append("\nContent:\n" + main_text)

    return "\n".join(text_parts).strip()


# ============================================================
# BUILD DOCUMENTS FOR RAG
# ============================================================

docs = []  # each item: {"id": ..., "text": ..., "metadata": {...}}

for node, attrs in G.nodes(data=True):
    if not should_embed(node, attrs):
        continue

    text = build_node_text(node, attrs)
    if not text.strip():
        continue

    doc = {
        "id": node,
        "text": text,
        "metadata": {
            "type": attrs.get("type"),
            "tag": attrs.get("tag"),
            # cheap page_name from node id – you can add more if needed
            "page_name": get_page_name_from_node_id(node),
        },
    }
    docs.append(doc)

print(f"Prepared {len(docs)} documents for embedding.")


# ============================================================
# LOCAL EMBEDDING MODEL
# ============================================================

embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def embed_batch(texts, batch_size=32):
    """
    Embed a batch of texts locally using SentenceTransformers.

    Returns a numpy array of shape (len(texts), dim).
    """
    embeddings = embedding_model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,  # cosine similarity → dot product
    )
    return embeddings


print("\n================= EXAMPLE DOCUMENTS =================")
for d in docs[:8]:   # print first 8 examples
    print("\n---", d["metadata"]["type"], "----------------------------------")
    print(d["text"])
    print("-----------------------------------------------------")


# ============================================================
# BUILD / SAVE EMBEDDING INDEX
# ============================================================

INDEX_FILE = "dom_embeddings.json"

if docs:
    texts = [d["text"] for d in docs]

    embeddings = embed_batch(texts)

    embedded_docs = []
    for doc, emb in zip(docs, embeddings):
        embedded_docs.append(
            {
                "id": doc["id"],
                "embedding": emb.tolist(),  # numpy → list for JSON
                "text": doc["text"],
                "metadata": doc["metadata"],
            }
        )

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(embedded_docs, f, ensure_ascii=False, indent=2)

    print(
        f"Created embeddings for {len(embedded_docs)} documents and saved to {INDEX_FILE}"
    )
else:
    print("No documents selected for embedding.")


# ============================================================
# SIMPLE RAG RETRIEVAL PIPELINE
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


def rag_query(query: str, top_k: int = 5):
    """
    Simple RAG retrieval:
    - embeds the query
    - computes cosine similarity (dot product, since normalized)
    - returns top_k best-matching nodes with their text.
    """
    ids, texts, metas, embs = load_index()

    # query embedding (normalized, same as docs)
    q_emb = embed_batch([query])[0]  # shape (dim,)
    sims = embs @ q_emb  # (num_docs, dim) · (dim,) → (num_docs,)

    top_indices = np.argsort(-sims)[:top_k]

    results = []
    for idx in top_indices:
        results.append(
            {
                "node_id": ids[idx],
                "score": float(sims[idx]),
                "text": texts[idx],
                "metadata": metas[idx],
            }
        )
    return results


# ============================================================
# DEMO / SANITY CHECK
# ============================================================

if __name__ == "__main__":
    print("\n===== Simple RAG demo =====")
    user_query = input("Enter a query (or leave empty to skip): ").strip()

    if user_query:
        matches = rag_query(user_query, top_k=5)

        print(f"\nTop {len(matches)} matching nodes:\n")
        for i, m in enumerate(matches, start=1):
            print(f"#{i}")
            print(f"Node ID: {m['node_id']}")
            print(f"Score:   {m['score']:.4f}")
            print("Text:")
            print(m["text"])
            print("-" * 80)

        # Also just print the node_ids as requested
        print("\nBest matching node_ids:")
        for m in matches:
            print(m["node_id"])
    else:
        print("No query entered; skipping RAG demo.")
