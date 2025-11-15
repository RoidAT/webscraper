import networkx as nx
import json
import matplotlib.pyplot as plt

# --- 1. Load Graph from JSON ---

with open('website_graph.json', 'r') as f:
    graph_json_string = f.read()


graph_data = json.loads(graph_json_string)
G_loaded = nx.node_link_graph(graph_data)

# --- 2. Visualization ---
plt.figure(figsize=(15, 10))
pos = nx.spring_layout(G_loaded, k=0.1, iterations=50, seed=42)

# Separate nodes by type
page_nodes = [n for n, data in G_loaded.nodes(data=True) if data.get('type') == 'Page']
section_nodes = [n for n, data in G_loaded.nodes(data=True) if data.get('type') == 'Section']
content_nodes = [n for n, data in G_loaded.nodes(data=True) if data.get('type') == 'Content']
data_nodes = [n for n, data in G_loaded.nodes(data=True) if data.get('type') == 'Data']

# Draw Nodes using the CORRECT FUNCTION: nx.draw_networkx_nodes
nx.draw_networkx_nodes(G_loaded, pos, nodelist=page_nodes, node_color='#72A0C1', node_size=3000, label='Page', alpha=0.9, linewidths=2, edgecolors='#4682B4')
nx.draw_networkx_nodes(G_loaded, pos, nodelist=section_nodes, node_color='#90EE90', node_size=1500, label='Section', alpha=0.9)
nx.draw_networkx_nodes(G_loaded, pos, nodelist=content_nodes, node_color='#F08080', node_size=800, label='Content', alpha=0.7)
nx.draw_networkx_nodes(G_loaded, pos, nodelist=data_nodes, node_color='#FFD700', node_size=500, label='Data', alpha=0.9)

# Draw Edges using the CORRECT FUNCTION: nx.draw_networkx_edges
page_link_edges = [e for e in G_loaded.edges(data=True) if e[2].get('relation') == 'LINKS_TO_PAGE']
structure_edges = [e for e in G_loaded.edges(data=True) if e[2].get('relation') == 'CONTAINS_SECTION']
content_edges = [e for e in G_loaded.edges(data=True) if e[2].get('relation') == 'HAS_CONTENT']
data_edges = [e for e in G_loaded.edges(data=True) if e[2].get('relation') == 'CONTAINS_DATA']

nx.draw_networkx_edges(G_loaded, pos, edgelist=page_link_edges, edge_color='#4682B4', style='solid', width=2.0, arrowsize=25)
nx.draw_networkx_edges(G_loaded, pos, edgelist=structure_edges, edge_color='gray', style='dashed', width=0.8, arrowsize=10)
nx.draw_networkx_edges(G_loaded, pos, edgelist=content_edges, edge_color='#F08080', style='dotted', width=1.0, arrowsize=10)
nx.draw_networkx_edges(G_loaded, pos, edgelist=data_edges, edge_color='#FFD700', style='solid', width=1.0, arrowsize=15)

# Create Node Labels
labels = {}
for node in G_loaded.nodes():
    data = G_loaded.nodes[node]
    label = data.get('title') or data.get('text') or data.get('label') or node
    if data.get('type') == 'Page':
        labels[node] = node
    else:
        labels[node] = label.replace("The nicest Spice Wreath...", "Blog Post").split(':')[0][:25] + "..." if len(label) > 25 else label

# Draw Labels using the CORRECT FUNCTION: nx.draw_networkx_labels
nx.draw_networkx_labels(G_loaded, pos, labels=labels, font_size=8, font_color='black')

plt.title("Graph RAG DOM Structure Visualization", size=15)
plt.legend(scatterpoints=1, title="Node Types")
plt.axis('off')
plt.savefig('dom_graph_visualization.png')
print("Visualization saved to dom_graph_visualization.png")