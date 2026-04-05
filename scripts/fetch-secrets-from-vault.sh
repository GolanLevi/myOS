#!/usr/bin/env bash
set -euo pipefail

MANIFEST="/srv/myos-config/secret-manifest.json"
OUT_DIR="/run/myos-secrets"

if [ ! -f "$MANIFEST" ]; then
  echo "Missing manifest: $MANIFEST"
  exit 1
fi

install -d -m 0750 -o root -g myos-runtime "$OUT_DIR"

VAULT_ID=$(jq -r '.vault_id' "$MANIFEST")
if [ -z "$VAULT_ID" ] || [ "$VAULT_ID" = "REPLACE_WITH_VAULT_OCID_AFTER_FIRST_APPLY" ]; then
  echo "vault_id not configured in $MANIFEST"
  exit 1
fi

count=$(jq '.secrets | length' "$MANIFEST")
for ((i=0; i<count; i++)); do
  name=$(jq -r ".secrets[$i].name" "$MANIFEST")
  target=$(jq -r ".secrets[$i].target_file" "$MANIFEST")
  mode=$(jq -r ".secrets[$i].mode // \"0400\"" "$MANIFEST")
  tmp=$(mktemp)
  oci --auth instance_principal secrets secret-bundle get-secret-bundle-by-name \
    --secret-name "$name" \
    --vault-id "$VAULT_ID" \
    --query 'data."secret-bundle-content".content' \
    --raw-output | base64 -d > "$tmp"
  install -o root -g myos-runtime -m "$mode" "$tmp" "$OUT_DIR/$target"
  rm -f "$tmp"
done

echo "vault secrets fetched to $OUT_DIR"
