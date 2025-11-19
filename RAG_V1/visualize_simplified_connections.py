import json
import networkx as nx
from pyvis.network import Network


# ============================================================
# 1. LOAD GRAPH
# ============================================================

GRAPH_FILE = "dom_graph.json"

with open(GRAPH_FILE, "r", encoding="utf-8") as f:
    graph_data = json.load(f)

# Use the same format as node_link_data (default edges key is "links")
G = nx.node_link_graph(graph_data, edges="links")

print("Loaded graph:")
print("  Nodes:", len(G.nodes))
print("  Edges:", len(G.edges))


# ============================================================
# 2. FIND ALL PATHS ENDING IN INTERNAL / EXTERNAL PAGES
# ============================================================

# We consider as "terminal link" edges:
# - LINKS_TO_PAGE           (internal .html)
# - LINKS_TO_EXTERNAL_PAGE  (external http/https)
TERMINAL_RELATIONS = {"LINKS_TO_PAGE", "LINKS_TO_EXTERNAL_PAGE"}

valid_paths = []   # list[list[node_id]]


def dfs_paths(start):
    """
    DFS from a start node; record paths that end in:
      - LINKS_TO_PAGE
      - LINKS_TO_EXTERNAL_PAGE
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
print(f"\nValid link paths (internal + external): {len(valid_paths)}")


# ============================================================
# 3. BUILD FULL LINK SUBGRAPH (LIKE IN LINK VISUALIZER)
# ============================================================

nodes_in_sub = set()
edges_in_sub = set()  # (u, v, key)

for path in valid_paths:
    # Nodes along the path
    for node in path:
        nodes_in_sub.add(node)

    # Edges along the path
    for i in range(len(path) - 1):
        u = path[i]
        v = path[i + 1]
        edge_dict = G.get_edge_data(u, v, default={})
        for key in edge_dict.keys():
            edges_in_sub.add((u, v, key))

print("Nodes in link-subgraph (unique):", len(nodes_in_sub))
print("Edges in link-subgraph (unique):", len(edges_in_sub))

SUB = nx.MultiDiGraph()

# Add nodes with attributes
for node in nodes_in_sub:
    SUB.add_node(node, **G.nodes[node])

# Add edges with attributes
for (u, v, key) in edges_in_sub:
    attrs = G.get_edge_data(u, v)[key]
    SUB.add_edge(u, v, key=key, **attrs)

print("SUB nodes:", len(SUB.nodes))
print("SUB edges:", len(SUB.edges))


# ============================================================
# 4. DETERMINE IMPORTANT NODES TO KEEP
# ============================================================

important_nodes = set()

for node, attrs in SUB.nodes(data=True):
    t = attrs.get("type", "")
    tag = attrs.get("tag", "")

    # Always keep:
    # - internal pages
    # - external pages
    # - anchor tags
    if t in {"Page_File", "External_Page"} or tag == "a":
        important_nodes.add(node)

# Also keep branching / junction nodes:
for node in SUB.nodes:
    out_deg = SUB.out_degree(node)
    in_deg = SUB.in_degree(node)

    # Node that splits or merges paths
    if out_deg > 1 or in_deg > 1:
        important_nodes.add(node)

print("Important nodes (pages, links, branches):", len(important_nodes))


# ============================================================
# 5. BUILD SIMPLIFIED GRAPH BY COMPRESSING CHAINS
# ============================================================

SIM = nx.DiGraph()   # simplified, no need for parallel edges
edge_set = set()     # for deduplication (u, v)


# Copy important nodes with attributes
for node in important_nodes:
    SIM.add_node(node, **SUB.nodes[node])


def walk_to_next_important(start):
    """
    From a neighbor 'start' that is NOT important,
    walk forward through non-important nodes until we hit
    another important node or get stuck.
    """
    current = start
    visited = set()

    while current not in important_nodes:
        if current in visited:
            return None  # cycle
        visited.add(current)

        succs = list(SUB.successors(current))
        if len(succs) != 1:
            # If we hit a branch or dead end before an important node, stop
            return None

        current = succs[0]

    return current


# For each important node, connect it directly to next important nodes
for u in important_nodes:
    for _, v, attrs in SUB.out_edges(u, data=True):
        if v in important_nodes:
            # Direct connection between important nodes
            if (u, v) not in edge_set:
                SIM.add_edge(u, v, relation=attrs.get("relation", ""))
                edge_set.add((u, v))
        else:
            # Compress path through non-important nodes
            target = walk_to_next_important(v)
            if target is not None and (u, target) not in edge_set:
                # We don't propagate intermediate relations here; just mark "COMPRESSED"
                SIM.add_edge(u, target, relation="COMPRESSED_PATH")
                edge_set.add((u, target))


print("SIM nodes:", len(SIM.nodes))
print("SIM edges:", len(SIM.edges))


# ============================================================
# 6. VISUALIZE SIMPLIFIED GRAPH
# ============================================================

COLOR_MAP = {
    "Page_File": "#ffcc00",       # internal page
    "External_Page": "#ff9900",   # external page
    "DOM_Element": "#66b3ff",     # for anchors / branch nodes
    "Section_Heading": "#009933",
    "Paragraph": "#3366cc",
    "Data_Link": "#ff6666",
}

def get_color_sim(node):
    t = SIM.nodes[node].get("type", "")
    return COLOR_MAP.get(t, "#cccccc")


def get_label_sim(node):
    data = SIM.nodes[node]
    t = data.get("type", "")
    tag = data.get("tag", "")

    if t == "Page_File":
        return "📄 " + data.get("title", node)

    if t == "External_Page":
        hostname = data.get("hostname")
        url = data.get("url", node)
        label = data.get("label") or hostname or url
        return "🌐 " + label

    if tag == "a":
        # link anchor node
        snippet = data.get("text_snippet", "") or data.get("label", "")
        return "🔗 " + (snippet[:40] + ("..." if len(snippet) > 40 else ""))

    # Branch / generic node
    return f"<{tag}>" if tag else node


def get_size_sim(node):
    data = SIM.nodes[node]
    t = data.get("type", "")
    tag = data.get("tag", "")

    if t == "Page_File":
        return 45
    if t == "External_Page":
        return 40
    if tag == "a":
        return 30   # anchors
    # branch or other important nodes
    return 20


net = Network(
    height="900px",
    width="100%",
    directed=True,
    notebook=False
)

for node, attrs in SIM.nodes(data=True):
    net.add_node(
        node,
        label=get_label_sim(node),
        color=get_color_sim(node),
        title=json.dumps(attrs, indent=2),
        size=get_size_sim(node),
        shape="dot",
    )

for u, v, attrs in SIM.edges(data=True):
    rel = attrs.get("relation", "")
    net.add_edge(u, v, title=rel, label=rel)

OUTPUT_FILE = "dom_graph_simplified_overview.html"
net.write_html(OUTPUT_FILE)

print(f"\nSimplified overview visualization saved: {OUTPUT_FILE}")
print("It shows pages (internal & external), link anchors, and branching nodes with compressed paths between them.")
