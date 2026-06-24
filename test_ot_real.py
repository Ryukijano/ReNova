import requests

# 1. Search for disease
search_query = """
query SearchDisease($queryString: String!) {
  search(queryString: $queryString, entityNames: ["disease"]) {
    hits {
      id
      name
      entity
    }
  }
}
"""

payload = {"query": search_query, "variables": {"queryString": "Parkinson's disease"}}
r = requests.post("https://api.platform.opentargets.org/api/v4/graphql", json=payload)
print("Search Status:", r.status_code)
search_data = r.json()
print("Search Response:", search_data)

# Extract first disease ID
hits = search_data.get("data", {}).get("search", {}).get("hits", [])
if hits:
    efo_id = hits[0]["id"]
    print("Found EFO ID:", efo_id)
    
    # 2. Query associated targets
    targets_query = """
    query AssociatedTargetsByEfo($efoId: String!) {
      disease(efoId: $efoId) {
        name
        associatedTargets {
          rows {
            target {
              id
              approvedSymbol
              proteinIds {
                id
                source
              }
            }
            score
          }
        }
      }
    }
    """
    
    payload2 = {"query": targets_query, "variables": {"efoId": efo_id}}
    r2 = requests.post("https://api.platform.opentargets.org/api/v4/graphql", json=payload2)
    print("Targets Status:", r2.status_code)
    print("Targets Response:", r2.json())
else:
    print("No disease found.")
