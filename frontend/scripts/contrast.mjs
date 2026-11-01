import { readFile, writeFile } from 'node:fs/promises'
const css = await readFile('src/tokens.css', 'utf8')
const blocks = css.split("[data-theme='dark']")
const parse = (text) =>
  Object.fromEntries([...text.matchAll(/--([\w-]+):\s*(#[0-9a-f]+);/g)].map((m) => [m[1], m[2]]))
const light = parse(blocks[0]),
  dark = { ...light, ...parse(blocks[1]) }
function luminance(hex) {
  let h = hex.slice(1)
  if (h.length === 3) h = [...h].map((c) => c + c).join('')
  return [0, 2, 4]
    .map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0)
}
const results = []
for (const [theme, tokens] of [
  ['light', light],
  ['dark', dark],
]) {
  const pairs = ['text', 'muted', 'faint'].flatMap((ink) =>
    ['surface', 'bg', 'column', 'hover'].map((bg) => [ink, bg])
  )
  pairs.push(...['accent', 'green', 'blue', 'amber', 'danger', 'purple'].map((ink) => [ink, ink + '-soft']), [
    'avatar-ink',
    'avatar',
  ])
  for (const [ink, background] of pairs) {
    const [a, b] = [luminance(tokens[ink]), luminance(tokens[background])].sort((x, y) => x - y)
    results.push({ theme, ink, background, ratio: Number(((b + 0.05) / (a + 0.05)).toFixed(2)) })
  }
}
const failures = results.filter((r) => r.ratio < 4.5)
await writeFile(
  '../docs/evidence/contrast.json',
  JSON.stringify(
    {
      note: 'Static foreground/background token pairs; not a complete rendered accessibility audit.',
      results,
      failures,
    },
    null,
    2
  ) + '\n'
)
console.log(
  JSON.stringify(
    { checked: results.length, minimumRatio: Math.min(...results.map((r) => r.ratio)), failures },
    null,
    2
  )
)
if (failures.length) process.exitCode = 1
