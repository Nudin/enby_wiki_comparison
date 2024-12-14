#!/usr/bin/env python3

from typing import Dict, List

import requests
from tabulate import tabulate


# Function to get articles from a Wikipedia category using PetScan
def get_articles_from_category(
    category: str, lang: str = "en", depth: int = 10
) -> List[str]:
    """Fetch all article titles from a Wikipedia category including subcategories using PetScan."""
    URL = "https://petscan.wmflabs.org/"

    params = {
        "language": lang,
        "project": "wikipedia",
        "categories": category,
        "depth": depth,
        "format": "plain",
        "ns[0]": "1",
        "doit": "1",
    }

    response = requests.get(URL, params=params, timeout=180)
    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        return []

    try:
        articles = response.text.strip().split("\n")
    except Exception as e:
        print(f"Error processing response: {e}")
        return []

    return articles


# Function to get Wikidata IDs for given Wikipedia pages
def get_wikidata_ids(articles: List[str], lang: str = "en") -> Dict[str, str]:
    """Fetch Wikidata IDs for given Wikipedia article titles."""
    S = requests.Session()
    URL = f"https://{lang}.wikipedia.org/w/api.php"

    params = {
        "action": "query",
        "format": "json",
        "prop": "pageprops",
        "ppprop": "wikibase_item",
        "titles": "|".join(articles),
    }

    response = S.get(url=URL, params=params)
    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        return {}

    try:
        data = response.json()
    except ValueError:
        print("Error parsing JSON response.")
        return {}

    wikidata_ids = {}

    for page in data.get("query", {}).get("pages", {}).values():
        if "pageprops" in page and "wikibase_item" in page["pageprops"]:
            wikidata_ids[page["title"]] = page["pageprops"]["wikibase_item"]

    return wikidata_ids


# Function to run a SPARQL query against Wikidata
def run_sparql_query(
    query: str, endpoint: str = "https://query.wikidata.org/sparql"
) -> List[Dict[str, str]]:
    """Run a SPARQL query against the Wikidata endpoint."""
    headers = {"Accept": "application/sparql-results+json"}

    response = requests.get(
        endpoint, params={"query": query}, headers=headers, timeout=600
    )
    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        return []

    try:
        data = response.json()
    except ValueError:
        print("Error parsing JSON response.")
        return []

    bindings = data.get("results", {}).get("bindings", [])

    return [
        {key: value.get("value", "") for key, value in binding.items()}
        for binding in bindings
    ]


# Generalized function to fill table columns based on language
def fill_table_columns(
    category: str, lang: str, articles: List[str], table_data: Dict[str, Dict[str, str]]
) -> None:
    """Fill table columns with data from a specific language Wikipedia."""
    for article in articles:
        if article not in table_data:
            table_data[article] = {"en": "", "de": "", "wikidata": ""}
        table_data[article][lang] = "nonbinary"


# Generate a comparison table and write as HTML
def generate_comparison_table(
    category_articles_en: List[str],
    category_articles_de: List[str],
    wikidata_results: List[Dict[str, str]],
) -> None:
    """Generate and print a table comparing category and Wikidata articles."""
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

    table = []
    table_data = {}
    for title in all_titles:
        if title in wikidata_set:
            en_status = (
                "nonbinary"
                if title in category_set_en
                else ("-" if not enwiki_map.get(title) else "wrong gender?")
            )
            de_status = (
                "nonbinary"
                if title in category_set_de
                else ("-" if not dewiki_map.get(title) else "wrong gender?")
            )
        else:
            en_status = "nonbinary" if title in category_set_en else "-"
            de_status = "nonbinary" if title in category_set_de else "-"

        wikidata_status = gender_map.get(title, "")
        table.append([title, en_status, de_status, wikidata_status])
        table_data[title] = {
            "en": en_status,
            "de": de_status,
            "wikidata": wikidata_status,
        }

    # Print ASCII table
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
<tr><th>Title</th><th>English Wikipedia</th><th>German Wikipedia</th><th>Wikidata</th></tr>
"""

    for row in table:
        html_page += "<tr>"
        for i, cell in enumerate(row):
            class_name = ""
            if i == 1 or i == 2:  # English or German Wikipedia columns
                if cell == "nonbinary":
                    class_name = "nonbinary"
                elif cell == "-":
                    class_name = "missing"
                elif cell == "wrong gender?":
                    class_name = "wrong"
            html_page += f"<td class='{class_name}'>{cell}</td>"
        html_page += "</tr>"

    html_page += """</table>
</body>
</html>"""

    with open("comparison_table.html", "w", encoding="utf-8") as html_file:
        html_file.write(html_page)


# Example usage
if __name__ == "__main__":
    # Get articles in English category
    category_en = "Non-binary people"
    articles_en = get_articles_from_category(category_en, lang="en")
    print(f"Articles in English category '{category_en}':", len(articles_en))

    # Get articles in German category
    category_de = "Nichtbinäre Person"
    articles_de = get_articles_from_category(category_de, lang="de")
    print(f"Articles in German category '{category_de}':", len(articles_de))

    # SPARQL query to fetch information about non-binary people
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
    print("SPARQL Query Results:", len(sparql_results))

    # Generate and print the comparison table
    generate_comparison_table(articles_en, articles_de, sparql_results)
