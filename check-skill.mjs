/**
 * html-ppt-maker 技能包的结构完整性检查。
 * 运行：node check-skill.mjs
 *
 * 这是个 DSH skill 包，不是应用——没有可跑的单测，但「能不能被正确加载」
 * 有一组明确条件：SKILL.md 的 frontmatter 完整、agent 定义可解析、
 * scripts 下的 Python 语法正确。这些坏一个，技能要么不出现，要么跑到一半炸。
 */
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const p = (...s) => join(ROOT, ...s);

let pass = 0;
const failures = [];
const check = (name, fn) => {
  try {
    fn();
    console.log(`PASS ${name}`);
    pass += 1;
  } catch (err) {
    console.log(`FAIL ${name}\n     ${err.message.split('\n')[0]}`);
    failures.push({ name, error: err });
  }
};

/** 极简 YAML frontmatter 解析：只取顶层的 key: value（够用了）。 */
function frontmatter(text) {
  const m = text.match(/^---\n([\s\S]*?)\n---/);
  if (!m) return null;
  const out = {};
  for (const line of m[1].split('\n')) {
    const kv = line.match(/^([a-zA-Z_-]+):\s*(.*)$/);
    if (kv) out[kv[1]] = kv[2].trim();
  }
  return out;
}

check('SKILL.md 存在且带 frontmatter', () => {
  const f = p('SKILL.md');
  assert.ok(existsSync(f), '缺少 SKILL.md');
  const fm = frontmatter(readFileSync(f, 'utf8'));
  assert.ok(fm, 'SKILL.md 没有 --- frontmatter ---');
  assert.ok(fm.name, 'frontmatter 缺 name');
  assert.ok(fm.description && fm.description.length > 20, 'frontmatter 的 description 太短或缺失（技能靠它被检索）');
  assert.equal(fm.name, 'html-ppt-maker', `name 是 ${fm.name}，与包名不一致`);
});

check('agents 定义存在且非空', () => {
  const dir = p('agents');
  assert.ok(existsSync(dir), '缺少 agents/');
  const files = readdirSync(dir).filter((f) => /\.(ya?ml|json)$/.test(f));
  assert.ok(files.length > 0, 'agents/ 下没有 .yaml/.json 定义');
  for (const f of files) {
    const body = readFileSync(join(dir, f), 'utf8');
    assert.ok(body.trim().length > 20, `${f} 内容过短`);
  }
});

check('要求的目录都在且非空', () => {
  for (const d of ['templates', 'examples', 'scripts']) {
    const dir = p(d);
    assert.ok(existsSync(dir), `缺少 ${d}/`);
    assert.ok(statSync(dir).isDirectory(), `${d} 不是目录`);
    const files = readdirSync(dir);
    assert.ok(files.length > 0, `${d}/ 是空的——技能会引用不存在的文件`);
  }
});

check('scripts 下的 Python 语法可解析', () => {
  const dir = p('scripts');
  const pys = readdirSync(dir).filter((f) => extname(f) === '.py');
  if (!pys.length) {
    console.log('     （scripts/ 下没有 .py，跳过）');
    return;
  }
  const bad = [];
  for (const f of pys) {
    const r = spawnSync('python3', ['-c', 'import ast,sys; ast.parse(open(sys.argv[1]).read())', join(dir, f)], {
      timeout: 20_000,
      encoding: 'utf8',
    });
    if (r.status !== 0) bad.push(`${f}: ${(r.stderr || '').split('\n').find((l) => l.trim()) ?? ''}`);
  }
  assert.equal(bad.length, 0, bad.join('；'));
});

check('package.json 能解析（若存在）', () => {
  const f = p('package.json');
  if (!existsSync(f)) {
    console.log('     （无 package.json，跳过）');
    return;
  }
  const pkg = JSON.parse(readFileSync(f, 'utf8'));
  assert.ok(pkg.name, 'package.json 缺 name');
});

check('资产文件没有零字节的（技能会引用它们）', () => {
  const dir = p('assets');
  if (!existsSync(dir)) {
    console.log('     （无 assets/，跳过）');
    return;
  }
  const empty = [];
  const walk = (d, depth = 0) => {
    if (depth > 3) return;
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const q = join(d, e.name);
      if (e.isDirectory()) walk(q, depth + 1);
      else if (statSync(q).size === 0) empty.push(q.replace(ROOT, ''));
    }
  };
  walk(dir);
  assert.equal(empty.length, 0, `零字节文件：${empty.slice(0, 3).join('、')}`);
});

console.log('');
console.log(`==== check-skill: ${pass} passed, ${failures.length} failed ====`);
if (failures.length) {
  for (const f of failures) {
    console.log(`FAILED: ${f.name}`);
    console.log(f.error?.stack ?? f.error);
  }
  process.exitCode = 1;
}
