#!/usr/bin/env node
// Dumps the FastAPI app's OpenAPI schema directly from Python (no running server
// required) so the generated TypeScript types always match the real backend contract.
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const repoRoot = dirname(frontendRoot)
const outFile = join(frontendRoot, 'openapi.json')

const venvPython =
  process.platform === 'win32'
    ? join(repoRoot, '.venv', 'Scripts', 'python.exe')
    : join(repoRoot, '.venv', 'bin', 'python')
const python = existsSync(venvPython) ? venvPython : 'python'

const code =
  'import json,sys; from app.main import app; json.dump(app.openapi(), sys.stdout, indent=2)'

const result = spawnSync(python, ['-c', code], {
  cwd: repoRoot,
  encoding: 'utf-8',
})

if (result.status !== 0) {
  console.error(result.stderr)
  process.exit(result.status ?? 1)
}

await import('node:fs/promises').then((fs) => fs.writeFile(outFile, result.stdout + '\n'))
console.log(`Wrote ${outFile}`)
