#!/usr/bin/env bash
set -euo pipefail

if ! command -v node >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
  echo "Node.js 18+ and npm/npx are required to install the APIMatic PayPal Context Plugin." >&2
  exit 1
fi
node -e 'const major=Number(process.versions.node.split(".")[0]); if(major<18){console.error("Node.js 18+ required");process.exit(1)}'

echo "Installing APIMatic PayPal Context Plugin into detected coding assistants..."
npx --yes context-plugins install paypal
echo "APIMatic PayPal Context Plugin installation command completed."
echo "Restart/reload your coding assistant and verify its MCP/context plugin list before relying on it."
