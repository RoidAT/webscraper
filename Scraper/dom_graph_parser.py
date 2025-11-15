import os
import re
import json
import networkx as nx
from bs4 import BeautifulSoup, Tag


# ============================================================
# 1. SETUP
# ============================================================

ROOT_DIR = "../StaticTestWebsite"     # ← change as needed
START_PAGE = ROOT_DIR + "/index.html"

file_contents = {}

# Load all HTML files
for filename in os.listdir(ROOT_DIR):
    if filename.endswith(".html"):
        with open(os.path.join(ROOT_DIR, filename), "r", encoding="utf-8") as f:
            file_contents[filename] = f.read()

all_known_pages = set(file_contents.keys())

G = nx.MultiDiGraph()
node_counters = {}   # per-page counters
node_map = {}        # reserved but not used


# ============================================================
# 2. HELPERS
# ============================================================

def get_node_id(page_name, tag):
    """Assign stable per-page, per-tag incremental IDs."""
    if page_name not in node_counters:
        node_counters[page_name] = {}

    tag_name = tag.name
    node_counters[page_name].setdefault(tag_name, 0)

    idx = node_counters[page_name][tag_name]
    node_counters[page_name][tag_name] += 1

    return f"{page_name}_{tag_name}_{idx}"


def get_simple_xpath(tag):
    """
    Generate a robust simple XPath for traceability.
    Only counts sibling tags of the same name.
    """
    path = []
    current = tag

    for parent in tag.parents:
        if parent.name == "[document]":
            break

        # Only count same-name siblings
        same_tag_siblings = [
            s for s in parent.find_all(current.name, recursive=False)
        ]

        if current not in same_tag_siblings:
            # BeautifulSoup sometimes changes tree during parsing
            break

        index = same_tag_siblings.index(current) + 1
        path.insert(0, f"{current.name}[{index}]")

        current = parent

    return "/" + "/".join(path)


def clean_text(s):
    """Normalize whitespace for consistent text extraction."""
    return " ".join(s.split())


def extract_link_text(a_tag):
    """Extract readable link text, falling back to <img alt> or 'Link'."""
    txt = a_tag.get_text(strip=True)
    if txt:
        return txt[:50]

    img = a_tag.find("img", alt=True)
    if img:
        return img["alt"][:50]

    return "Link"


# ============================================================
# 3. DOM TRAVERSAL
# ============================================================

def build_dom_tree(element, parent_node_id, page_name, depth=0):
    if not isinstance(element, Tag):
        return

    if element.name in ["script", "style", "meta", "link", "br", "hr"]:
        return

    # -----------------------------
    # Create node for this element
    # -----------------------------
    node_id = get_node_id(page_name, element)

    text_content = clean_text(element.get_text())

    node_attrs = {
        "type": "DOM_Element",
        "tag": element.name,
        "xpath": get_simple_xpath(element),
        "page": page_name,
        "depth": depth,
        "text_snippet": text_content[:150]
    }

    # Tag-specific node types
    if element.name == "title":
        node_attrs["type"] = "Page_Title"
        node_attrs["title_text"] = text_content

    elif element.name in ["h1", "h2", "h3", "h4"]:
        node_attrs["type"] = "Section_Heading"
        node_attrs["heading_text"] = text_content

    elif element.name == "p" and text_content:
        node_attrs["type"] = "Paragraph"
        node_attrs["full_text"] = text_content

    G.add_node(node_id, **node_attrs)

    # Parent → Child containment
    if parent_node_id:
        G.add_edge(parent_node_id, node_id, relation="CONTAINS")

    # -----------------------------
    # Process <a> links
    # -----------------------------
    if element.name == "a" and element.has_attr("href"):
        href = element["href"].split("#")[0]
        link_txt = extract_link_text(element)
        target = href.split("/")[-1]

        if target in all_known_pages:
            # Page → Page link edge
            G.add_edge(node_id, target, relation="LINKS_TO_PAGE", anchor=link_txt)


        elif re.match(r"^(http|https)", href):

            # External web page (not email/phone)

            external_node_id = href  # use full URL as node ID to merge duplicates

            # Create the external page node if not present

            if external_node_id not in G:
                G.add_node(

                    external_node_id,

                    type="External_Page",

                    url=href,

                    label=link_txt,

                    hostname=re.sub(r"^https?://", "", href).split("/")[0]  # domain

                )

            G.add_edge(node_id, external_node_id, relation="LINKS_TO_EXTERNAL_PAGE", anchor=link_txt)


        elif re.match(r"^(mailto:|tel:)", href):

            # Non-page external target (email, phone)

            data_node_id = f"{page_name}_DATA_{len(G.nodes)}"

            G.add_node(

                data_node_id,

                type="Data_Link",

                data_type=href.split(":")[0],

                value=href,

                label=link_txt

            )

            G.add_edge(node_id, data_node_id, relation="CONTAINS_DATA", anchor=link_txt)

    # -----------------------------
    # Recurse into children
    # -----------------------------
    for child in element.children:
        if isinstance(child, Tag):
            build_dom_tree(child, node_id, page_name, depth + 1)


# ============================================================
# 4. PROCESS ALL PAGES
# ============================================================

for filename, content in file_contents.items():
    soup = BeautifulSoup(content, "html.parser")

    page_node = filename
    title = soup.title.string.strip() if soup.title else filename
    G.add_node(page_node, type="Page_File", title=title)

    # Use <html> or <body> or document root
    root = soup.find("html") or soup.find("body") or soup
    build_dom_tree(root, page_node, filename, depth=0)


# ============================================================
# 5. EXPORT GRAPH
# ============================================================

graph_data = nx.node_link_data(G)
json_string = json.dumps(graph_data, indent=4)

with open("dom_graph.json", "w", encoding="utf-8") as f:
    f.write(json_string)

print("--- DOM Graph Created ---")
print("Nodes:", len(G.nodes))
print("Edges:", len(G.edges))
print("Saved to dom_graph.json")
