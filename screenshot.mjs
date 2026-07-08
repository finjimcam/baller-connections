// Host-run screenshot tool (per CLAUDE.md workflow).
// Usage: node screenshot.mjs <url> [label]
// Saves to ./temporary screenshots/screenshot-N[-label].png (auto-incremented).

import { mkdir, readdir } from 'node:fs/promises'
import path from 'node:path'
import puppeteer from 'puppeteer'

const url = process.argv[2]
const label = process.argv[3]

if (!url) {
  console.error('Usage: node screenshot.mjs <url> [label]')
  process.exit(1)
}

const dir = path.join(process.cwd(), 'temporary screenshots')
await mkdir(dir, { recursive: true })

const existing = await readdir(dir)
let max = 0
for (const file of existing) {
  const match = /^screenshot-(\d+)/.exec(file)
  if (match) max = Math.max(max, Number(match[1]))
}
const name = `screenshot-${max + 1}${label ? `-${label}` : ''}.png`
const outPath = path.join(dir, name)

const browser = await puppeteer.launch({ headless: 'shell' })
try {
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 })
  await page.goto(url, { waitUntil: 'networkidle0', timeout: 60_000 })
  // small settle delay for physics/animations to come to rest
  await new Promise((resolve) => setTimeout(resolve, 2500))
  await page.screenshot({ path: outPath, fullPage: true })
  console.log(outPath)
} finally {
  await browser.close()
}
