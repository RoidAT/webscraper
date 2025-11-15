import networkx as nx
from bs4 import BeautifulSoup
import re
import json

# --- 1. Website Data Input ---
# In a real environment, you would use:
file_contents = {}
with open('../StaticTestWebsite/index.html', 'r') as f: file_contents['index.html'] = f.read()

# List of all known pages (important for determining internal links)
all_known_pages = set(file_contents.keys()) | {
    "product.html", "wreaths.html", "blog-post.html", "product-item.html",
    "spice-bouqet2.html", "spice-wreath.html", "spice-wreath2.html"
}

# --- 2. Graph Building Function ---
G = nx.MultiDiGraph()


def extract_dom_and_links(page_name, html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    page_title = soup.title.string.strip() if soup.title else page_name
    G.add_node(page_name, type="Page", title=page_title)

    for tag_name in ['h1', 'h2', 'h3']:
        for i, heading in enumerate(soup.find_all(tag_name)):
            heading_text = heading.get_text().strip()
            if not heading_text: continue

            node_id = f"{page_name}_{tag_name}_{i}"
            G.add_node(node_id, type="Section", text=heading_text, tag=tag_name)
            G.add_edge(page_name, node_id, relation="CONTAINS_SECTION", anchor=None)

            if heading.find_next_sibling('p'):
                p_text = heading.find_next_sibling('p').get_text().strip()
                if p_text:
                    data_id = f"{page_name}_p_{i}"
                    G.add_node(data_id, type="Content", text=p_text, tag="p")
                    G.add_edge(node_id, data_id, relation="HAS_CONTENT", anchor=None)

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].split('#')[0]
        link_text = a_tag.get_text(strip=True) or 'Link'
        link_text = link_text.replace('\n', ' ').replace('\t', '').strip()[:50]

        if href.endswith('.html') and href in all_known_pages and href != page_name:
            # Inter-page links
            G.add_edge(page_name, href, relation="LINKS_TO_PAGE", anchor=link_text)
        elif re.match(r'^(mailto:|tel:)', href) or href.startswith('http'):
            # Data/External links
            data_id = f"{page_name}_data_{len(G.nodes)}"
            G.add_node(data_id, type="Data", data_type=href.split(':')[0], value=href, label=link_text)
            G.add_edge(page_name, data_id, relation="CONTAINS_DATA", anchor=link_text)


# Process all files
for filename, content in file_contents.items():
    extract_dom_and_links(filename, content)

# --- 3. Save Graph to JSON String ---
output_path = "./"
graph_data = nx.node_link_data(G)
graph_json_string = json.dumps(graph_data, indent=4)
print(graph_json_string)

file_path = f"{output_path}website_graph.json" # output_path is "./"
with open(file_path, 'w') as f:
    f.write(graph_json_string)

print(f"\nGraph successfully saved to: {file_path}")