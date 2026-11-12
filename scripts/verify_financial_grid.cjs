const fs = require('node:fs');
const path = require('node:path');
const file = path.join(__dirname, '..', 'frontend', 'src', 'pages', 'FinancialLifecycle.tsx');
const source = fs.readFileSync(file, 'utf8');
const required = [
  "field:'id'", "field:'case_type'", "field:'customer'", "field:'product'",
  "field:'batch'", "field:'amount'", "field:'status'", "field:'policy_result'",
  "field:'ai_suggestion'", "field:'evidence_count'", "field:'net_result'",
  "field:'decision'", "field:'decided_by'"
];
const missing = required.filter(token => !source.includes(token));
const actions = {
  AGGrid: source.includes('<AgGridReact'),
  CSVExport: source.includes('exportDataAsCsv()'),
  QuickSearch: source.includes('quickFilterText={quickSearch}'),
  StatusChips: source.includes("['OPEN','UNDER_REVIEW','APPROVED','REJECTED']"),
  RowInvestigation: source.includes('onRowClicked={e=>setSelected(e.data)}'),
  SavedFilters: source.includes('merchantos.savedFilter'),
  ComplaintClustering: source.includes('/complaint-clusters/run')
};
if (missing.length || Object.values(actions).some(value => !value)) {
  console.error(JSON.stringify({missingColumns: missing, actions}, null, 2));
  process.exit(1);
}
console.log('PASS: all 13 required financial case columns and 7 grid/clustering interactions are present.');
