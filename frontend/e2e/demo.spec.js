// The competition demo story, driven through the real UI against the real API.
import { expect, test } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const LICENCE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../docs/demo-assets/sample-product-licence.pdf')
const ITEM = `Viral Transport Medium Swab Kit, 3 mL ${Date.now() % 100000}`

async function as(page, username) {
  await page.goto('/login')
  await page.evaluate(async (u) => {
    const r = await fetch('/api/auth/demo-login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: u }) })
    localStorage.setItem('lives_one_token', (await r.json()).access_token)
  }, username)
}

async function select(page, key, value) { await page.locator(`#f-${key}`).selectOption(value) }

test.describe.serial('LIVES ONE demo: Amy item request → approvals → SAP → regional intelligence', () => {
  let requestNumber

  test('Act 1 — Amy creates an item; validation blocks the missing regulatory evidence', async ({ page }) => {
    await page.goto('/login')
    await page.getByRole('button', { name: /Amy.*Product Manager/ }).click()
    await expect(page).toHaveURL(/\/mdm\/requests|\/$/)
    await page.goto('/mdm/new')
    await page.getByRole('button', { name: /Item \/ Material/ }).click()
    await page.getByRole('button', { name: 'Continue' }).click()
    await page.locator('#f-item_name').fill(ITEM)
    await page.locator('#f-item_description').fill('Flocked swab with 3 mL viral transport medium, 50-pack')
    await select(page, 'product_family', 'Product A')
    await select(page, 'item_category', 'Consumable')
    await select(page, 'unit_of_measure', 'BOX')
    await page.locator('#f-manufacturer').fill('Meditrans Biologics')
    await page.locator('#f-manufacturer_part_no').fill(`MTB-VTM-3ML-50-${Date.now() % 1000}`)
    await select(page, 'regulatory_class', 'Class B')
    await select(page, 'storage_condition', 'Ambient')
    await select(page, 'stock_managed', 'Yes')
    await page.waitForTimeout(900)
    await page.locator('button.btn-primary', { hasText: 'Check for duplicates' }).click()
    // Blocked: conditional regulatory fields and evidence are mandatory for Class B.
    await expect(page.getByText(/Product registration \/ licence number is required/)).toBeVisible()
    await expect(page.getByText('Incomplete', { exact: true })).toBeVisible()
    await page.locator('#f-licence_number').fill('HSA-DE-2026-0815')
    await page.locator('#f-licence_expiry').fill('2028-06-30')
    await page.locator('#docs input[type=file]').first().setInputFiles(LICENCE)
    await expect(page.getByText(/Uploaded sample-product-licence.pdf/).first()).toBeVisible()
    await page.waitForTimeout(900)
    await page.locator('button.btn-primary', { hasText: 'Check for duplicates' }).click()
    // Explainable near-duplicate against the existing 3 mL kit.
    await expect(page.getByText('Viral Transport Medium Kit, 3 mL').first()).toBeVisible()
    await page.getByRole('button', { name: /Continue with justification|Not a duplicate/ }).first().click()
    const dialog = page.getByRole('dialog')
    if (await dialog.isVisible()) {
      await dialog.locator('textarea').fill('New 50-pack with its own manufacturer part number; existing record is the single kit.')
      await dialog.getByRole('button', { name: 'Record decision' }).click()
    }
    await expect(page.getByText('Duplicate review recorded.')).toBeVisible()
    await page.locator('button.btn-primary', { hasText: 'Review & submit' }).click()
    await page.getByRole('button', { name: /Submit for approval/ }).click()
    const done = page.getByRole('dialog', { name: 'Request submitted' })
    await expect(done).toBeVisible()
    requestNumber = (await done.locator('h3').textContent()).trim()
    expect(requestNumber).toMatch(/^MDM-\d{4}-\d+$/)
  })

  test('Act 2 — parallel approvals, then sequential Business Support', async ({ page }) => {
    for (const user of ['siti', 'daniel', 'kevin']) {
      await as(page, user)
      await page.goto('/flow/inbox')
      const card = page.locator('article.task', { hasText: requestNumber })
      await expect(card).toBeVisible()
      await card.getByRole('button', { name: 'Approve' }).click()
      await page.getByRole('dialog').getByRole('button', { name: 'Approve' }).click()
      await expect(card).toHaveCount(0)
    }
  })

  test('Act 2 — Priya verifies and creates the record through the mock SAP adapter', async ({ page }) => {
    await as(page, 'priya')
    await page.goto('/')
    await page.getByRole('link', { name: new RegExp(requestNumber) }).first().click()
    await expect(page.getByRole('button', { name: /Verify & create in SAP B1/ })).toBeVisible()
    for (const box of await page.locator('.action-bar input[type=checkbox]').all()) await box.check()
    await page.getByRole('button', { name: /Verify & create in SAP B1/ }).click()
    await expect(page.getByText(/Live in SAP B1:/)).toBeVisible()
    await expect(page.locator('.callout.ok .mono')).toHaveText(/^MOCK-I\d+/)
    await expect(page.getByText('Simulated SAP confirmation')).toBeVisible()
    await expect(page.getByText('SAP creation completed').first()).toBeVisible()
  })

  test('Act 2 — Amy is notified of completion', async ({ page }) => {
    await as(page, 'amy')
    await page.goto('/')
    await page.getByRole('button', { name: /Notifications/ }).click()
    await expect(page.getByRole('dialog', { name: 'Notifications' }).getByText(new RegExp(`${requestNumber} is live`))).toBeVisible()
  })

  test('Act 3 — Marcus filters the regional view and assigns a sales follow-up', async ({ page }) => {
    await as(page, 'marcus')
    await page.goto('/growth/regional')
    await expect(page.getByText('Country × product matrix')).toBeVisible()
    await page.getByRole('button', { name: 'Malaysia' }).click()
    await expect(page).toHaveURL(/countries=MY/)
    await expect(page.locator('.chart-card').first()).toBeVisible()
    await page.goto('/growth/opportunities')
    await page.getByRole('button', { name: /Cross-selling/ }).click()
    await page.locator('article.opp').first().click()
    const dlg = page.getByRole('dialog')
    await expect(dlg.getByText('2 · Supporting data')).toBeVisible()
    await dlg.getByLabel('Assign to').selectOption({ label: 'Nurul · Account Manager · Malaysia' })
    await dlg.getByLabel('Note', { exact: true }).fill('Please review clinical fit before contacting.')
    await dlg.getByRole('button', { name: /Create follow-up/ }).click()
    await expect(dlg.getByText(/Follow-up → Nurul/)).toBeVisible()
  })

  test('Server-side access control: Amy cannot open regional analytics', async ({ page }) => {
    await as(page, 'amy')
    await page.goto('/growth/regional')
    await expect(page.getByText(/does not have access/)).toBeVisible()
    const status = await page.evaluate(async () => (await fetch('/api/analytics/overview', { headers: { Authorization: `Bearer ${localStorage.getItem('lives_one_token')}` } })).status)
    expect(status).toBe(403)
  })
})
