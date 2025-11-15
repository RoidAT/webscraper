import json
import networkx as nx
from pyvis.network import Network


# ============================================================
# LOAD GRAPH
# ============================================================

GRAPH_FILE = "dom_graph.json"

with open(GRAPH_FILE, "r", encoding="utf-8") as f:
    graph_data = json.load(f)

# Explicitly set edges="links" to match nx.node_link_data default
G = nx.node_link_graph(graph_data, edges="links")


# ============================================================
# COLOR MAP
# ============================================================

COLOR_MAP = {
    "Page_File":     "#ffcc00",
    "External_Page": "#ff9900",
    "DOM_Element":   "#66b3ff",
    "Section_Heading": "#009933",
    "Paragraph":     "#3366cc",
    "Data_Link":     "#ff6666",
}

def get_node_color(node):
    t = G.nodes[node].get("type", "")
    return COLOR_MAP.get(t, "#cccccc")


# ============================================================
# NODE LABELS
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

    if t == "Paragraph":
        return "P: " + data.get("text_snippet", "")[:40] + "..."

    if t in ["Section_Heading", "Page_Title"]:
        return data.get("heading_text") or data.get("title_text") or node

    if t == "Data_Link":
        return "🔗 " + data.get("value", "")

    # Fallback: generic tag
    return f"<{data.get('tag', '')}> {node}"


# ============================================================
# NODE SIZE BASED ON TEXT CONTENT
# ============================================================

def get_node_size(node, k=0.2, base=10):
    """Return a node size based on its text content length."""
    data = G.nodes[node]
    t = data.get("type", "")

    if t == "Page_File":
        return 50  # keep internal page nodes big
    if t == "External_Page":
        return 40  # external pages slightly smaller but still prominent

    text_fields = [
        data.get("full_text", ""),
        data.get("heading_text", ""),
        data.get("title_text", ""),
        data.get("text_snippet", "")
    ]

    text = " ".join([txt for txt in text_fields if txt])
    weight = len(text)

    # Prevent absurdly tiny or huge nodes
    return min(max(base + k * weight, 15), 120)


# ============================================================
# BUILD INTERACTIVE VISUALIZATION
# ============================================================

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
        size=get_node_size(node)
    )

# Add edges
for u, v, attrs in G.edges(data=True):
    rel = attrs.get("relation", "")
    net.add_edge(u, v, title=rel, label=rel)


# ============================================================
# OUTPUT
# ============================================================

OUTPUT_FILE = "dom_graph_visualization.html"
net.write_html(OUTPUT_FILE)

print(f"Interactive visualization saved: {OUTPUT_FILE}")
