import json
import networkx as nx
import numpy as np
import os

from Embedding.embed_graph import GRAPH_FILE, get_context_text, model, OUTPUT_EMBEDDINGS


def main():
    print("Loading graph...")
    with open(GRAPH_FILE, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    G = nx.node_link_graph(graph_data)

    os.makedirs("Embedding/Output_Embeddings", exist_ok=True)

    # --------------------------------------------------------
    # 1) PREPARE CONTEXT TEXTS IN ONE LIST
    # --------------------------------------------------------
    print("Preparing context texts...")
    node_ids = list(G.nodes)
    all_texts = [get_context_text(G, node) for node in node_ids]

    # --------------------------------------------------------
    # 2) BATCH EMBEDDING (very fast)
    # --------------------------------------------------------
    print("Embedding all nodes (batched)...")

    embeddings_matrix = model.encode(
        all_texts,
        convert_to_numpy=True,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True
    )

    print("Embedding shape:", embeddings_matrix.shape)

    # --------------------------------------------------------
    # 3) BUILD OUTPUT JSON
    # --------------------------------------------------------
    print("Saving embeddings...")

    output_dict = {}

    for i, node in enumerate(node_ids):
        attrs = G.nodes[node]
        output_dict[node] = {
            "context": all_texts[i],
            "embedding": embeddings_matrix[i].tolist(),
            "type": attrs.get("type"),
            "page": attrs.get("page")
        }

    with open(OUTPUT_EMBEDDINGS, "w", encoding="utf-8") as f:
        json.dump(output_dict, f, indent=4)

    print("✔ Embeddings created!")
    print(f"Saved to {OUTPUT_EMBEDDINGS}")


if __name__ == "__main__":
    main()
