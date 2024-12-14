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


# Function to fill table columns with data from specific language Wikipedia
def fill_table_columns(
    category: str, lang: str, articles: List[str], table_data: Dict[str, Dict[str, str]]
) -> None:
    """Fill table columns with data from a specific language Wikipedia."""
    for article in articles:
        if article not in table_data:
            table_data[article] = {"en": "", "de": "", "wikidata": ""}
        table_data[article][lang] = "non-binary"


# Function to generate comparison table and save as HTML
def collate(
    category_articles_en: List[str],
    category_articles_de: List[str],
    wikidata_results: List[Dict[str, str]],
) -> None:
    """Generate and print a table comparing category and Wikidata articles, and save as HTML."""
    category_set_en = set(category_articles_en)
    category_set_de = set(category_articles_de)
    wikidata_set = {result.get("enwiki", "") for result in wikidata_results}

    gender_map = {
        result.get("enwiki", ""): result.get("genderLabel", "")
        for result in wikidata_results
    }
    enwiki_map = {
        result.get("enwiki", ""): result.get("enwiki", "")
        for result in wikidata_results
    }
    dewiki_map = {
        result.get("enwiki", ""): result.get("dewiki", "")
        for result in wikidata_results
    }

    all_titles = sorted(category_set_en | category_set_de | wikidata_set)

    table_data = {}
    for title in all_titles:
        en_status = (
            "non-binary"
            if title in category_set_en
            else ("-" if not enwiki_map.get(title) else "wrong gender?")
        )
        de_status = (
            "non-binary"
            if title in category_set_de
            else ("-" if not dewiki_map.get(title) else "wrong gender?")
        )
        wikidata_status = gender_map.get(title, "")
        table_data[title] = {
            "en": en_status,
            "de": de_status,
            "wikidata": wikidata_status,
        }

    return table_data


def generate_comparison_table(
    table_data,
    output_html_file: str = "comparison_table.html",
):
    # Print ASCII table
    table = [[k, v["en"], v["de"], v["wikidata"]] for k, v in table_data.items()]
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
