import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const cli = fileURLToPath(new URL('../node_modules/@playwright/test/cli.js', import.meta.url));
// Resolve the locked environment once, then own the Python child directly so
// restart tests stop only their fixture process (including on Windows).
const python = spawnSync('uv', ['run', '--locked', 'python', '-c', 'import sys; print(sys.executable)'], {
  cwd: fileURLToPath(new URL('../..', import.meta.url)), encoding: 'utf8',
});
if (python.error || python.status !== 0) {
  console.error(python.error?.message ?? python.stderr); process.exit(1);
}
const child = spawn(process.execPath, [cli, 'test'], {
  cwd: fileURLToPath(new URL('..', import.meta.url)),
  env: { ...process.env, B1_API_INTEGRATION: '1', B1_API_PYTHON: python.stdout.trim() }, stdio: 'inherit',
});
child.on('error', error => { console.error(error.message); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
