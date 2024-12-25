#!/usr/bin/env python3

from typing import Dict, List

import numpy as np
import pandas as pd
import requests
from tabulate import tabulate

# Constants
PETS_CAN_URL = "https://petscan.wmflabs.org/"
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_URL_TEMPLATE = "https://{lang}.wikipedia.org/w/api.php"


def get_articles_from_category(
    category: str, lang: str = "en", depth: int = 10
) -> List[Dict[str, str]]:
    """Fetch all article titles from a Wikipedia category including subcategories using PetScan."""
    params = {
        "language": lang,
        "project": "wikipedia",
        "categories": category,
        "depth": depth,
        "format": "json",
        "ns[0]": 1,  # Namespace parameter
        "doit": "1",  # Execute the query
        "wikidata_item": "any",
        "common_wiki": "auto",
    }
    project = f"{lang}wiki"

    try:
        # Make the request to the Petscan API
        response = requests.get(PETS_CAN_URL, params=params, timeout=180)
        response.raise_for_status()

        # Parse the JSON response
        data = response.json()

        # Navigate to results in the nested structure
        results = []
        if "*" in data:
            for page in data["*"][0]["a"]["*"]:
                wikidata = page.get("metadata", {}).get("wikidata")
                title = page.get("title")
                if wikidata and title:
                    results.append(
                        {
                            "qid": wikidata,
                            project: title.replace("_", " "),
                            f"{project}_gender": "non-binary",
                        }
                    )

        return results

    except requests.RequestException as e:
        print(f"Error during request: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return []


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
    category_articles_en: List[Dict[str, str]],
    category_articles_de: List[Dict[str, str]],
    wikidata_results: List[Dict[str, str]],
) -> None:
    """Generate and print a table comparing category and Wikidata articles, and save as HTML."""
    wd_df = pd.DataFrame.from_dict(wikidata_results)

    # Replace wikidata-url by qid column
    wd_df["qid"] = wd_df["enby"].apply(url2qid)
    wd_df = wd_df.drop(columns=["enby"])

    wd_df = wd_df.rename(
        columns={
            "enbyLabel": "wikidata",
            "enbyDescription": "description",
            "genderLabel": "wikidata_gender",
        }
    )

    de_df = pd.DataFrame.from_dict(category_articles_de)
    en_df = pd.DataFrame.from_dict(category_articles_en)
    merged = pd.merge(
        pd.merge(wd_df, de_df, on=["qid", "dewiki"], how="outer"),
        en_df,
        on=["qid", "enwiki"],
        how="outer",
    )
    merged.fillna(np.nan, inplace=True)
    merged.replace([np.nan], [None], inplace=True)

    return merged


def generate_comparison_table(
    table_data,
    output_html_file: str = "comparison_table.html",
):
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

    for idx, row in table_data.iterrows():
        html_page += "<tr>"
        name = row.get("wikidata") or row.get("enwiki") or row.get("dewiki")
        html_page += f"<td>{name}</td>"
        for project in ["enwiki", "dewiki"]:
            site = row.get(f"{project}")
            gender = row.get(f"{project}_gender")
            if not site:
                cell = "no article"
                class_name = "missing"
            elif not gender:
                cell = "wrong gender?"
                class_name = "wrong"
            else:
                cell = gender
                class_name = "nonbinary"
            html_page += f"<td class='{class_name}'>{cell}</td>"
        # Wikidata is different
        site = row.get(f"wikidata")
        gender = row.get(f"wikidata_gender")
        if not site or not gender:
            cell = "wrong gender?"
            class_name = "wrong"
        else:
            cell = gender
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
    SELECT DISTINCT ?enby ?enbyLabel ?enbyDescription (group_concat(distinct ?genderLabel;separator=", ") as ?wikidata_gender) ?dewiki ?enwiki WHERE {
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
        ?gender rdfs:label ?genderLabel FILTER (lang(?genderLabel) = "en") .
    } group by ?enby ?enbyLabel ?enbyDescription ?dewiki ?enwiki
    """
    sparql_results = run_sparql_query(wikidata_query)
    print(f"SPARQL results: {len(sparql_results)}")

    # Generate and print the comparison table
    generate_comparison_table(collate(articles_en, articles_de, sparql_results))
