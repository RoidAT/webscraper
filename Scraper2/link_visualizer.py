import json
import networkx as nx
from pyvis.network import Network


# ============================================================
# 1. LOAD GRAPH
# ============================================================

GRAPH_FILE = "Output_Graph_Json/dom_graph.json"

with open(GRAPH_FILE, "r", encoding="utf-8") as f:
    graph_data = json.load(f)

# Use the same format as node_link_data (default is "links")
G = nx.node_link_graph(graph_data)

print("Loaded graph:")
print("  Nodes:", len(G.nodes))
print("  Edges:", len(G.edges))


# ============================================================
# 2. FIND ALL PATHS ENDING IN INTERNAL OR EXTERNAL PAGE LINKS
# ============================================================

valid_paths = []   # list[list[node_id]]

# We now treat BOTH as terminal:
# - LINKS_TO_PAGE              (internal .html page)
# - LINKS_TO_EXTERNAL_PAGE     (external http/https page)
TERMINAL_RELATIONS = {"LINKS_TO_PAGE", "LINKS_TO_EXTERNAL_PAGE"}


def dfs_paths(start):
    """
    DFS from a start node; record paths that end in:
      - LINKS_TO_PAGE           (internal page)
      - LINKS_TO_EXTERNAL_PAGE  (external page)
    """
    stack = [(start, [start])]

    while stack:
        node, path = stack.pop()

        for _, nxt, attrs in G.out_edges(node, data=True):
            rel = attrs.get("relation", "")

            # Avoid trivial cycles
            if nxt in path:
                continue

            new_path = path + [nxt]

            if rel in TERMINAL_RELATIONS:
                valid_paths.append(new_path)
            else:
                stack.append((nxt, new_path))


# Run DFS starting from every node
for node in G.nodes:
    dfs_paths(node)

# Deduplicate paths
valid_paths = [list(p) for p in {tuple(p) for p in valid_paths}]
print(f"\nValid paths ending in internal or external page links: {len(valid_paths)}")


# ============================================================
# 3. COLLECT NODES & EDGES FOR SUBGRAPH
# ============================================================

nodes_in_sub = set()
edges_in_sub = set()  # (u, v, key)

for path in valid_paths:
    # Add all nodes in this path
    for node in path:
        nodes_in_sub.add(node)

    # Add all edges along this path
    for i in range(len(path) - 1):
        u = path[i]
        v = path[i + 1]

        edge_dict = G.get_edge_data(u, v, default={})
        for key in edge_dict.keys():
            edges_in_sub.add((u, v, key))


print("Nodes in subgraph (unique):", len(nodes_in_sub))
print("Edges in subgraph (unique):", len(edges_in_sub))


# ============================================================
# 4. BUILD SUBGRAPH EXPLICITLY (NO DATA LOSS)
# ============================================================

SUB = nx.MultiDiGraph()

# Add nodes with ALL their attributes
for node in nodes_in_sub:
    SUB.add_node(node, **G.nodes[node])

# Add edges with their original attributes
for (u, v, key) in edges_in_sub:
    attrs = G.get_edge_data(u, v)[key]
    SUB.add_edge(u, v, key=key, **attrs)

print("Subgraph nodes:", len(SUB.nodes))
print("Subgraph edges:", len(SUB.edges))


# ============================================================
# 5. VISUALIZE SUBGRAPH
# ============================================================

COLOR_MAP = {
    "Page_File": "#ffcc00",       # internal pages
    "External_Page": "#ff9900",   # external pages (new)
    "DOM_Element": "#66b3ff",
    "Section_Heading": "#009933",
    "Paragraph": "#3366cc",
    "Data_Link": "#ff6666",
}

def get_color(node):
    t = SUB.nodes[node].get("type", "")
    return COLOR_MAP.get(t, "#cccccc")


def get_label(node):
    data = SUB.nodes[node]
    t = data.get("type", "")

    if t == "Page_File":
        return "📄 " + data.get("title", node)

    if t == "External_Page":
        # show hostname or URL; fall back to node id
        hostname = data.get("hostname")
        url = data.get("url", node)
        label = data.get("label") or hostname or url
        return "🌐 " + label

    if t in ["Section_Heading", "Page_Title"]:
        return data.get("heading_text") or data.get("title_text") or node

    if t == "Paragraph":
        txt = data.get("text_snippet", "")
        return f"P: {txt[:40]}..."

    if t == "Data_Link":
        return "🔗 " + data.get("value", "")

    return f"<{data.get('tag', '')}>"


def get_size(node):
    t = SUB.nodes[node].get("type", "")
    if t == "Page_File":
        return 45          # internal page
    if t == "External_Page":
        return 40          # external page
    if t == "DOM_Element":
        return 15
    return 20


net = Network(
    height="900px",
    width="100%",
    directed=True,
    notebook=False
)

for node, attrs in SUB.nodes(data=True):
    net.add_node(
        node,
        label=get_label(node),
        color=get_color(node),
        title=json.dumps(attrs, indent=2),  # hover to see all fields, including url/hostname
        size=get_size(node),
        shape="dot",
    )

for u, v, key, attrs in SUB.edges(data=True, keys=True):
    rel = attrs.get("relation", "")
    net.add_edge(u, v, title=rel, label=rel)


OUTPUT_FILE = "Output_Graph_Visualization/dom_graph_link_paths.html"
net.write_html(OUTPUT_FILE)

print(f"\nVisualization saved: {OUTPUT_FILE}")
print("Internal (📄) and external (🌐) pages should now both appear as terminal nodes.")
