#!/usr/bin/env python3

from typing import Dict, List

import numpy as np
import pandas as pd
import requests
from pandas.core.reshape.api import merge
from tabulate import tabulate

# Constants
PETS_CAN_URL = "https://petscan.wmflabs.org/"
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIPEDIA_API_URL_TEMPLATE = "https://{lang}.wikipedia.org/w/api.php"

LANG_CODES = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
}
CATEGORIES = {
    "en": "Non-binary_people",
    "de": "Nichtbinäre_Person",
    "fr": "Personnalité_non_binaire",
    "es": "Personas no binarias",
}


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
    wikidata_results: List[Dict[str, str]],
    wikis: Dict[str, List[Dict[str, str]]],
) -> None:
    """Generate and print a table comparing category and Wikidata articles, and save as HTML."""
    wd_df = pd.DataFrame.from_dict(wikidata_results)

    # Replace wikidata-url by qid column
    wd_df["qid"] = wd_df["enby"].apply(url2qid)
    wd_df.drop(columns=["enby"], inplace=True)

    wd_df.rename(
        columns={
            "enbyLabel": "wikidata",
            "enbyDescription": "description",
            "genderLabel": "wikidata_gender",
        },
        inplace=True,
    )

    merged = wd_df
    for projectname, data in wikis.items():
        df = pd.DataFrame.from_dict(data)
        merged = merged.merge(df, on=["qid", projectname], how="outer")

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
<script src="sort.js"></script>
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
    .hidden{
        display: none;
    }
    th {
        cursor: pointer;
        background-color: #f9f9f9;
    }
    th.sorted-asc::after {
        content: " ▲";
    }
    th.sorted-desc::after {
        content: " ▼";
    }
    a {
        color: black;
        text-decoration: none
    }
</style>
</head>
<body>
<h1>Comparison Table</h1>
<p>Non-binary people on Wikipedia and Wikidata</p>
<p>Green: Non-binary, Grey: No article, Red: Binary gender (likely Wrong?)</p>
<p>Click on the column headers to sort the table</p>
<input type="checkbox" id="filterCheckbox">Show only potential errors</input>
<table>
<thead>
<tr>
    <th>Title</th>
"""
    for lang in LANG_CODES.keys():
        html_page += f"<th>{LANG_CODES[lang]} Wikipedia</th>"
    html_page += """
    <th>Wikidata</th>
</tr>
</thead>
"""

    for idx, row in table_data.iterrows():
        error = False

        # Start building the row
        keys = ["wikidata"] + [f"{lang}wiki" for lang in LANG_CODES.keys()]
        name = next((row.get(key) for key in keys if row.get(key)), None)
        row_html = f""

        row_html += f"<td>{name}</td>"

        for lang in LANG_CODES.keys():
            project = f"{lang}wiki"
            site = row.get(f"{project}")
            gender = row.get(f"{project}_gender")

            if not site:
                cell = "no article"
                class_name = "missing"
            elif not gender:
                cell = "wrong gender?"
                class_name = "wrong"
                error = True
            else:
                cell = gender
                class_name = "nonbinary"

            if site:
                row_html += f"<td class='{class_name}'><a href=\"https://{lang}.wikipedia.org/wiki/{site}\">{cell}</a></td>"
            else:
                row_html += f"<td class='{class_name}'>{cell}</td>"

        # Wikidata is different
        site = row.get(f"wikidata")
        qid = row.get(f"qid")
        gender = row.get(f"wikidata_gender")

        if not site or not gender:
            cell = "wrong gender?"
            class_name = "wrong"
            error = True
        else:
            cell = gender
            class_name = "nonbinary"

        if qid:
            row_html += f"<td class='{class_name}'><a href=\"https://www.wikidata.org/wiki/{qid}\">{cell}</a></td>"
        else:
            row_html += f"<td class='{class_name}'>{cell}</td>"

        # Close the row with a conditional class if error is true
        row_class = "error" if error else ""
        row_html = f"<tr class='{row_class}'>{row_html}</tr>"

        # Append the row to the full HTML table
        html_page += row_html

    html_page += """</table>
</body>
</html>"""

    with open(output_html_file, "w", encoding="utf-8") as html_file:
        html_file.write(html_page)


# Main program
if __name__ == "__main__":
    # Wikipedia categories
    wikipedia = {}
    for lang in LANG_CODES.keys():
        projectname = f"{lang}wiki"
        wikipedia[projectname] = get_articles_from_category(CATEGORIES[lang], lang=lang)
        print(f"Articles in {LANG_CODES[lang]} category: {len(wikipedia[projectname])}")

    # Wikidata query
    wikidata_query = """
    SELECT DISTINCT ?enby ?enbyLabel ?enbyDescription (group_concat(distinct ?genderLabel;separator=", ") as ?wikidata_gender) ?dewiki ?enwiki ?frwiki ?eswiki WHERE {
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
      OPTIONAL {
        ?enby ^schema:about ?articlefr .
        ?articlefr schema:isPartOf <https://fr.wikipedia.org/>;
                   schema:name ?frwiki .
      }
      OPTIONAL {
        ?enby ^schema:about ?articlees .
        ?articlees schema:isPartOf <https://es.wikipedia.org/>;
                   schema:name ?eswiki .
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en". }
        ?gender rdfs:label ?genderLabel FILTER (lang(?genderLabel) = "en") .
    } group by ?enby ?enbyLabel ?enbyDescription ?dewiki ?enwiki ?frwiki ?eswiki
    """
    sparql_results = run_sparql_query(wikidata_query)
    print(f"SPARQL results: {len(sparql_results)}")

    # Generate and print the comparison table
    generate_comparison_table(
        collate(
            sparql_results,
            wikipedia,
        )
    )
