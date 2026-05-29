import { mkdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from 'playwright'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const webDir = path.resolve(__dirname, '..')
const repoRoot = path.resolve(webDir, '..')
const outputDir = path.join(repoRoot, 'assets', 'readme')

const appBaseUrl = process.env.AOI_APP_BASE_URL || 'http://127.0.0.1:5173'
const apiBaseUrl = process.env.AOI_API_BASE_URL || 'http://127.0.0.1:8000'

function fail(message) {
  throw new Error(message)
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options)
  const text = await response.text()
  let payload = null

  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }

  if (!response.ok) {
    const detail =
      typeof payload === 'object' && payload !== null
        ? payload.message || payload.detail || JSON.stringify(payload)
        : String(payload || response.statusText)
    fail(`${options.method || 'GET'} ${url} failed: ${detail}`)
  }

  return payload
}

async function seedReviewRun() {
  const payload = {
    model_version: 'vision-2.4.1',
    images: [
      {
        image_path: `${appBaseUrl}/mock/pcb-example-2nd.png`,
        image_role: 'full_board',
        image_width: 1454,
        image_height: 1010,
      },
    ],
    events: [
      {
        pcb_id: 'PCB-README-REVIEW',
        component_id: 'U001',
        inspection_result: 'PASS',
        defect_type: 'NO_DEFECT',
        confidence_score: 0.99,
        inference_latency_ms: 24,
        run_image_index: 0,
        overlay_x: 0.11,
        overlay_y: 0.16,
        overlay_width: 0.05,
        overlay_height: 0.08,
        overlay_shape: 'rect',
      },
      {
        pcb_id: 'PCB-README-REVIEW',
        component_id: 'U002',
        inspection_result: 'FAIL',
        defect_type: 'MISALIGNMENT',
        confidence_score: 0.81,
        inference_latency_ms: 26,
        run_image_index: 0,
        overlay_x: 0.25,
        overlay_y: 0.15,
        overlay_width: 0.05,
        overlay_height: 0.09,
        overlay_shape: 'rect',
      },
      {
        pcb_id: 'PCB-README-REVIEW',
        component_id: 'U003',
        inspection_result: 'FAIL',
        defect_type: 'INSUFFICIENT_SOLDER',
        confidence_score: 0.77,
        inference_latency_ms: 22,
        run_image_index: 0,
        overlay_x: 0.35,
        overlay_y: 0.15,
        overlay_width: 0.05,
        overlay_height: 0.09,
        overlay_shape: 'rect',
      },
      {
        pcb_id: 'PCB-README-REVIEW',
        component_id: 'U004',
        inspection_result: 'PASS',
        defect_type: 'NO_DEFECT',
        confidence_score: 0.96,
        inference_latency_ms: 25,
        run_image_index: 0,
        overlay_x: 0.47,
        overlay_y: 0.15,
        overlay_width: 0.05,
        overlay_height: 0.08,
        overlay_shape: 'rect',
      },
      {
        pcb_id: 'PCB-README-REVIEW',
        component_id: 'U005',
        inspection_result: 'PASS',
        defect_type: 'NO_DEFECT',
        confidence_score: 0.99,
        inference_latency_ms: 27,
        run_image_index: 0,
        overlay_x: 0.13,
        overlay_y: 0.49,
        overlay_width: 0.04,
        overlay_height: 0.06,
        overlay_shape: 'rect',
      },
    ],
  }

  const response = await requestJson(`${apiBaseUrl}/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return response.run_id
}

async function seedSetupRun() {
  const created = await requestJson(`${apiBaseUrl}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pcb_id: 'PCB-README-SETUP' }),
  })

  const runId = created.run.id
  const imageBytes = await readFile(path.join(webDir, 'public', 'mock', 'pcb-example-4th.png'))

  await requestJson(`${apiBaseUrl}/runs/${runId}/images`, {
    method: 'POST',
    headers: { 'Content-Type': 'image/png' },
    body: imageBytes,
  })

  await requestJson(`${apiBaseUrl}/runs/${runId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model_name: 'MB-GAMMA-4L',
      requires_fiducials: true,
      requires_barcode: true,
    }),
  })

  return runId
}

async function buildPage(browser, runId) {
  const context = await browser.newContext({
    viewport: { width: 1680, height: 1180 },
    deviceScaleFactor: 1,
  })

  await context.addInitScript((selectedRunId) => {
    window.localStorage.setItem('aoi:selected-run-id', selectedRunId)
    window.localStorage.setItem('aoi:industrial-theme-enabled', 'true')
    window.localStorage.setItem('aoi:zen-mode-enabled', 'false')
    window.localStorage.setItem('aoi:dismissed-setup-runs', '{}')
    window.localStorage.removeItem('aoi:selected-images')
  }, runId)

  const page = await context.newPage()
  page.setDefaultTimeout(30000)
  await page.goto(appBaseUrl, { waitUntil: 'domcontentloaded' })
  await page.locator('.app-shell').waitFor()

  return { context, page }
}

async function captureReviewScreenshot(browser, runId) {
  const { context, page } = await buildPage(browser, runId)
  await page.locator('.review-panel').waitFor()
  await page.locator('.viewer-image').waitFor()
  await page.locator('.defect-list-item', { hasText: 'U003' }).click()
  await page.getByRole('button', { name: 'Center Defect' }).click()
  await page.waitForTimeout(600)
  await page.locator('.app-shell').screenshot({
    path: path.join(outputDir, 'review-workspace.png'),
  })
  await context.close()
}

async function captureSetupScreenshot(browser, runId) {
  const { context, page } = await buildPage(browser, runId)
  await page.locator('.setup-shell').waitFor()
  await page.locator('.setup-step-card', { hasText: 'Find Fiducial Marks' }).click()
  await page.locator('img[alt="Fiducial preview"]').waitFor()
  await page.waitForTimeout(600)
  await page.locator('.app-shell').screenshot({
    path: path.join(outputDir, 'setup-workflow.png'),
  })
  await context.close()
}

async function main() {
  await mkdir(outputDir, { recursive: true })

  await requestJson(`${apiBaseUrl}/health`).catch((error) => {
    fail(`AOI API is not reachable at ${apiBaseUrl}: ${error.message}`)
  })
  await fetch(appBaseUrl).catch((error) => {
    fail(`AOI frontend is not reachable at ${appBaseUrl}: ${error.message}`)
  })

  const [reviewRunId, setupRunId] = await Promise.all([seedReviewRun(), seedSetupRun()])

  const browser = await chromium.launch({ headless: true })
  try {
    await captureReviewScreenshot(browser, reviewRunId)
    await captureSetupScreenshot(browser, setupRunId)
  } finally {
    await browser.close()
  }

  console.log(`Saved README screenshots to ${outputDir}`)
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
})
