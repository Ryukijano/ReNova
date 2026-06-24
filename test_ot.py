import requests
import json

q = """
query AssociatedTargets($disease: String!) {
  disease(searchTerm: $disease) {
    name
    associatedTargets {
      rows {
        target {
          id
          approvedSymbol
          uniprotIds
        }
        score
      }
    }
  }
}
"""

payload = {"query": q, "variables": {"disease": "Parkinson's disease"}}
headers = {"Content-Type": "application/json"}

r = requests.post("https://api.platform.opentargets.org/api/v4/graphql", json=payload, headers=headers)
print("Status:", r.status_code)
print("Response:", r.text)
