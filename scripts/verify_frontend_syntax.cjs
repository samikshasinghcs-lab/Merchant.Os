const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const root = path.resolve(__dirname, '..', 'frontend', 'src');
const files = [];
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full);
    else if (/\.(tsx?|jsx?)$/.test(entry.name) && !entry.name.endsWith('.d.ts')) files.push(full);
  }
}
walk(root);
const errors = [];
for (const file of files) {
  const kind = file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, kind);
  for (const diagnostic of source.parseDiagnostics) {
    const pos = source.getLineAndCharacterOfPosition(diagnostic.start || 0);
    errors.push(`${path.relative(root, file)}:${pos.line + 1}:${pos.character + 1} ${ts.flattenDiagnosticMessageText(diagnostic.messageText, ' ')}`);
  }
}
if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}
console.log(`Frontend syntax check passed: ${files.length} TypeScript/TSX source files parsed.`);
