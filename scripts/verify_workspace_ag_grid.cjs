const fs = require('node:fs');
const path = require('node:path');
const file = path.join(__dirname, '..', 'app', 'static', 'app.js');
const source = fs.readFileSync(file, 'utf8');
const start = source.indexOf('MERCHANTOS — AG GRID FINANCIAL OPERATIONS WORKSPACE');
const end = source.indexOf('MERCHANTOS — WORKFLOW REPAIR', start);
if (start < 0 || end < 0) throw new Error('Server-rendered AG Grid integration block not found.');
const grid = source.slice(start, end);
const checks = {
  CommunityCDN: grid.includes('ag-grid-community@') && grid.includes('createGrid('),
  NoReactGrid: !grid.includes('AgGridReact'),
  MultiSelect: grid.includes("rowSelection: 'multiple'") && grid.includes('getSelectedRows()'),
  StableRowIds: grid.includes('getRowId: params => String(params.data.id)'),
  GlobalSearch: grid.includes('quickFilterText'),
  ColumnFilters: grid.includes('floatingFilter: true'),
  StatusShortcuts: grid.includes('data-mos-status') && grid.includes('setFilterModel'),
  CsvExport: grid.includes('exportDataAsCsv({ fileName:'),
  SelectedCsv: grid.includes('onlySelected: true'),
  PersistedColumns: grid.includes('getColumnState()') && grid.includes('applyColumnState'),
  PersistedFilters: grid.includes('getFilterModel()') && grid.includes('setFilterModel'),
  Pagination: grid.includes('paginationPageSizeSelector: [10, 25, 50, 100]'),
  HumanApprovalActions: grid.includes("addButton('Approve'") && grid.includes("addButton('Reject'"),
  RefreshLoop: grid.includes('setInterval(refreshRefundGrid, 30000)'),
  TenantSafeBackendRoute: grid.includes("api('/refunds')")
};
const failed = Object.entries(checks).filter(([, ok]) => !ok).map(([name]) => name);
if (failed.length) {
  console.error('AG Grid verification failed:', failed.join(', '));
  process.exit(1);
}
console.log('PASS: server-rendered AG Grid Community integration, selection, filters, persistence, exports, pagination and approval guardrails verified.');
