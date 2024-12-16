#!/usr/bin/env python3

from typing import Dict, List

import requests
from tabulate import tabulate

# Constants
PETS_CAN_URL = "https://petscan.wmflabs.org/"
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_URL_TEMPLATE = "https://{lang}.wikipedia.org/w/api.php"


# Function to get articles from a Wikipedia category using PetScan
def get_articles_from_category(
    category: str, lang: str = "en", depth: int = 10
) -> List[str]:
    """Fetch all article titles from a Wikipedia category including subcategories using PetScan."""
    params = {
        "language": lang,
        "project": "wikipedia",
        "categories": category,
        "depth": depth,
        "format": "plain",
        "ns[0]": "1",
        "doit": "1",
    }
    response = requests.get(PETS_CAN_URL, params=params, timeout=180)
    if response.status_code != 200:
        raise ValueError(f"Error: Received status code {response.status_code}")
    return response.text.strip().split("\n") if response.text else []


# Function to get Wikidata IDs for given Wikipedia pages
def get_wikidata_ids(articles: List[str], lang: str = "en") -> Dict[str, str]:
    """Fetch Wikidata IDs for given Wikipedia article titles."""
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageprops",
        "ppprop": "wikibase_item",
        "titles": "|".join(articles),
    }
    response = requests.get(
        WIKIPEDIA_API_URL_TEMPLATE.format(lang=lang), params=params, timeout=180
    )
    response.raise_for_status()

    data = response.json().get("query", {}).get("pages", {})
    return {
        page.get("title"): page.get("pageprops", {}).get("wikibase_item")
        for page in data.values()
        if "pageprops" in page
    }


# Function to run a SPARQL query against Wikidata
def run_sparql_query(query: str) -> List[Dict[str, str]]:
    """Run a SPARQL query against the Wikidata endpoint."""
    headers = {"Accept": "application/sparql-results+json"}
    response = requests.get(
        WIKIDATA_SPARQL_ENDPOINT, params={"query": query}, headers=headers, timeout=600
    )
    response.raise_for_status()

    return [
        {key: value.get("value", "") for key, value in binding.items()}
        for binding in response.json().get("results", {}).get("bindings", [])
    ]


def url2qid(url: str):
    return url[31:]


def fetch_missing_wikidata_info(
    lang_code: str, missing_titles: List[str]
) -> List[Dict[str, str]]:
    """Fetch Wikidata information for missing articles."""
    titles_str = " ".join(
        f'"{title.replace('"', '\\"')}"@{lang_code}' for title in missing_titles
    )
    query = f"""
    SELECT DISTINCT ?item ?itemLabel ?itemDescription ?gender ?genderLabel ?dewiki ?enwiki WHERE {{
      VALUES ?enwiki {{ {titles_str} }}
      ?item ^schema:about ?article .
      ?article schema:isPartOf <https://{lang_code}.wikipedia.org/>;
              schema:name ?enwiki .
      OPTIONAL {{
        ?item wdt:P21 ?gender .
      }}
      OPTIONAL {{
        ?item ^schema:about ?article .
        ?article schema:isPartOf <https://en.wikipedia.org/>;
                 schema:name ?enwiki .
      }}
      OPTIONAL {{
        ?item ^schema:about ?articlede .
        ?articlede schema:isPartOf <https://de.wikipedia.org/>;
                   schema:name ?dewiki .
      }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en". }}
    }}
    """
    print(query)
    return run_sparql_query(query)


# Function to generate comparison table and save as HTML
def collate(
    category_articles_en: List[str],
    category_articles_de: List[str],
    wikidata_results: List[Dict[str, str]],
) -> None:
    """Generate and print a table comparing category and Wikidata articles, and save as HTML."""
    results = []
    for wdr in wikidata_results:
        qid = url2qid(wdr["enby"])
        wikidata_name = wdr.get("enbyLabel", qid)
        dewiki = wdr.get("dewiki")
        enwiki = wdr.get("enwiki")
        data = {
            "qid": qid,
            "wikidata_gender": wdr["genderLabel"],
            "wikidata_name": wikidata_name,
            "enwiki_name": enwiki,
            "dewiki_name": dewiki,
        }
        if dewiki:
            data["dewiki_gender"] = (
                "non-binary" if dewiki in category_articles_de else "wrong gender?"
            )
        if enwiki:
            data["enwiki_gender"] = (
                "non-binary" if enwiki in category_articles_en else "wrong gender?"
            )
        if dewiki or enwiki:
            results.append(data)

    en_in_wd = set(v.get("enwiki") for v in wikidata_results)
    de_in_wd = set(v.get("dewiki") for v in wikidata_results)
    set_en = set(category_articles_en)
    set_de = set(category_articles_de)
    missing_in_wd = (set_en - en_in_wd) | (set_de - de_in_wd)

    for name in missing_in_wd:
        data = {"wikidata_gender": "wrong gender?"}
        if name in set_de:
            data["dewiki_name"] = name
            data["dewiki_gender"] = "non-binary"
        else:
            data["dewiki_gender"] = "?"
        if name in set_en:
            data["enwiki_name"] = name
            data["enwiki_gender"] = "non-binary"
        else:
            data["enwiki_gender"] = "?"
        results.append(data)

    return results


def generate_comparison_table(
    table_data,
    output_html_file: str = "comparison_table.html",
):
    # Print ASCII table
    table = [
        [
            v.get("wikidata_name") or v.get("enwiki_name") or v.get("dewiki_name"),
            v.get("enwiki_gender") or "-",
            v.get("dewiki_gender") or "-",
            v.get("wikidata_gender"),
        ]
        for v in table_data
    ]
    table = sorted(table, key=lambda s: s[0] or "")
    print(
        tabulate(
            table,
            headers=["Title", "English Wikipedia", "German Wikipedia", "Wikidata"],
            tablefmt="grid",
        )
    )

    # Write HTML page with styled table
    html_page = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Comparison Table</title>
<style>
    body {
        font-family: Arial, sans-serif;
        margin: 20px;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin-top: 20px;
    }
    th, td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
    }
    th {
        background-color: #f2f2f2;
    }
    .nonbinary {
        background-color: lightgreen;
    }
    .missing {
        background-color: lightgrey;
    }
    .wrong {
        background-color: lightcoral;
    }
</style>
</head>
<body>
<h1>Comparison Table</h1>
<table>
<thead>
<tr><th>Title</th><th>English Wikipedia</th><th>German Wikipedia</th><th>Wikidata</th></tr>
</thead>
"""

    for row in table:
        html_page += "<tr>"
        for i, cell in enumerate(row):
            class_name = ""
            if i > 0:  # English or German Wikipedia columns
                if cell == "-":
                    class_name = "missing"
                elif cell == "wrong gender?":
                    class_name = "wrong"
                elif cell == "?":
                    class_name = "unknown"
                elif cell != "":
                    class_name = "nonbinary"
            html_page += f"<td class='{class_name}'>{cell}</td>"
        html_page += "</tr>"

    html_page += """</table>
</body>
</html>"""

    with open(output_html_file, "w", encoding="utf-8") as html_file:
        html_file.write(html_page)


# Main program
if __name__ == "__main__":
    # English Wikipedia category
    articles_en = get_articles_from_category("Non-binary people", lang="en")
    print(f"Articles in English category: {len(articles_en)}")

    # German Wikipedia category
    articles_de = get_articles_from_category("Nichtbinäre Person", lang="de")
    print(f"Articles in German category: {len(articles_de)}")

    # Wikidata query
    wikidata_query = """
    SELECT DISTINCT ?enby ?enbyLabel ?enbyDescription ?gender ?genderLabel ?dewiki ?enwiki WHERE {
      ?enby wdt:P31 wd:Q5 .
      ?enby wdt:P21/wdt:P279* wd:Q48270 .
      ?enby wdt:P21 ?gender .
      OPTIONAL {
        ?enby ^schema:about ?article .
        ?article schema:isPartOf <https://en.wikipedia.org/>;
                 schema:name ?enwiki .
      }
      OPTIONAL {
        ?enby ^schema:about ?articlede .
        ?articlede schema:isPartOf <https://de.wikipedia.org/>;
                   schema:name ?dewiki .
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en". }
    }
    """
    sparql_results = run_sparql_query(wikidata_query)
    print(f"SPARQL results: {len(sparql_results)}")

    # Generate and print the comparison table
    generate_comparison_table(collate(articles_en, articles_de, sparql_results))
