import json
import networkx as nx
from pyvis.network import Network


# ============================================================
# 1. LOAD GRAPH
# ============================================================

GRAPH_FILE = "dom_graph.json"

with open(GRAPH_FILE, "r", encoding="utf-8") as f:
    graph_data = json.load(f)

G = nx.node_link_graph(graph_data)

print("Loaded graph:")
print("  Nodes:", len(G.nodes))
print("  Edges:", len(G.edges))


# ============================================================
# 2. COLOR SETTINGS
# ============================================================

COLOR_MAP = {
    "Page_File": "#ffcc00",       # yellow
    "DOM_Element": "#66b3ff",     # blue
    "Section_Heading": "#009933", # green
    "Paragraph": "#3366cc",       # darker blue
    "Data_Link": "#ff6666",       # red
}


def get_node_color(node):
    data = G.nodes[node]

    node_type = data.get("type", "DOM_Element")
    return COLOR_MAP.get(node_type, "#cccccc")  # default gray


def get_node_label(node):
    """Readable labels for visualization."""
    data = G.nodes[node]
    t = data.get("type", "")

    if t == "Page_File":
        return f"📄 {data.get('title', node)}"

    if t in ["Section_Heading", "Page_Title"]:
        return data.get("heading_text") or data.get("title_text") or node

    if t == "Paragraph":
        txt = data.get("text_snippet", "")
        return f"P: {txt[:40]}..."

    if t == "Data_Link":
        return f"🔗 {data.get('value', '')}"

    # fallback: tag name
    tag = data.get("tag", "")
    return f"<{tag}> {node}"


# ============================================================
# 3. BUILD INTERACTIVE VISUALIZATION
# ============================================================

net = Network(
    height="900px",
    width="100%",
    directed=True,
    bgcolor="#ffffff",
    font_color="#000000"
)

net.barnes_hut(
    gravity=-20000,
    central_gravity=0.2,
    spring_length=170,
    spring_strength=0.01,
    damping=0.95,
)

# Add nodes with metadata
for node, attrs in G.nodes(data=True):
    net.add_node(
        node,
        label=get_node_label(node),
        color=get_node_color(node),
        title=json.dumps(attrs, indent=2),
        shape="dot",
        size=15 if attrs.get("type") != "Page_File" else 30
    )

# Add edges with tooltip showing relation
for u, v, attrs in G.edges(data=True):
    rel = attrs.get("relation", "")
    net.add_edge(u, v, title=rel, label=rel)


# ============================================================
# 4. GENERATE HTML VISUALIZATION
# ============================================================

OUTPUT_FILE = "dom_graph_visualization.html"
net.write_html(OUTPUT_FILE)

print(f"Interactive visualization saved to: {OUTPUT_FILE}")
print("Open it in a browser to explore the DOM graph.")
