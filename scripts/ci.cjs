#!/usr/bin/env node
'use strict';

const { path, repoRoot, stat, filesIn, run, main } = require('./lib/common.cjs');
const { checkDocs, checkRepo, checkActions } = require('./lib/checks.cjs');

main(() => {
  checkDocs(repoRoot);
  checkRepo(repoRoot);
  checkActions(repoRoot);
  for (const dir of ['scripts', 'tests']) {
    for (const file of filesIn(path.join(repoRoot, dir)).filter((file) => file.endsWith('.cjs'))) {
      run(process.execPath, ['--check', file]);
    }
  }
  run(process.execPath, ['--test', 'tests/tooling.test.cjs'], { stdio: 'inherit' });
  if (stat(path.join(repoRoot, 'pyproject.toml'))?.isFile()) {
    run('uv', ['run', '--locked', 'ruff', 'check', 'mini_learngraph'], { stdio: 'inherit' });
    run('uv', ['run', '--locked', 'pyright', 'mini_learngraph'], { stdio: 'inherit' });
    run('uv', ['run', '--locked', 'pytest'], { stdio: 'inherit' });
  }
  if (stat(path.join(repoRoot, 'web', 'package.json'))?.isFile()) {
    // Invoke npm's JS entry directly on Windows (spawnSync does not execute .cmd).
    const npmCli = process.env.npm_execpath || path.join(path.dirname(process.execPath), 'node_modules/npm/bin/npm-cli.js');
    const npm = (args) => {
      if (process.platform === 'win32' || process.env.npm_execpath) {
        run(process.execPath, [npmCli, '--prefix', 'web', ...args], { stdio: 'inherit' });
      } else {
        run('npm', ['--prefix', 'web', ...args], { stdio: 'inherit' });
      }
    };
    npm(['ci']);
    for (const script of ['typecheck', 'lint', 'test', 'build']) npm(['run', script]);
    const browserInstall = ['exec', '--', 'playwright', 'install'];
    if (process.platform === 'linux' && process.env.CI === 'true') browserInstall.push('--with-deps');
    npm([...browserInstall, 'chromium']);
    npm(['run', 'test:flow']);
    npm(['run', 'test:api-flow']);
  }
  console.log('基础 CI 检查通过');
});
