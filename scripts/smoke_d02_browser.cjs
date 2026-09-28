'use strict'

const { chromium } = require('playwright')

const baseURL = process.env.D02_BASE_URL || 'http://localhost:8080'

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage()
  const failed = []
  page.on('response', (response) => {
    if (response.url().startsWith(baseURL) && response.status() >= 400) {
      failed.push(`${response.status()} ${response.url()}`)
    }
  })

  const login = await page.goto(`${baseURL}/login`, { waitUntil: 'networkidle' })
  if (!login || login.status() !== 200) throw new Error('GET /login no devolvió 200')
  await page.locator('#app').waitFor()

  const direct = await page.goto(`${baseURL}/proformas/123`, { waitUntil: 'networkidle' })
  if (!direct || direct.status() !== 200) {
    throw new Error('El refresh directo de /proformas/123 no devolvió el index SPA')
  }
  if (!new URL(page.url()).pathname.startsWith('/login')) {
    throw new Error(`La guarda de sesión no redirigió a login: ${page.url()}`)
  }
  await page.locator('#app').waitFor()

  const health = await page.evaluate(async () => {
    const response = await fetch('/api/v1/health/')
    return { status: response.status, body: await response.json() }
  })
  if (health.status !== 200 || health.body.estado !== 'ok') {
    throw new Error(`Health API inválido: ${JSON.stringify(health)}`)
  }
  if (failed.length) throw new Error(`Recursos fallidos: ${failed.join(', ')}`)
  await browser.close()
  console.log('d02-browser-smoke-ok')
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
