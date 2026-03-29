# Visual regression baseline generation container.
#
# Uses the official Playwright image to ensure consistent font rendering
# and browser binaries across WSL2 local dev and Ubuntu CI environments.
# This eliminates OS-level rendering differences in screenshot baselines.
#
# Usage:
#   docker compose -f docker/docker-compose.playwright.yml run --rm playwright \
#     npx playwright test tests/e2e/visual-regression.spec.ts
#
# Update baselines:
#   docker compose -f docker/docker-compose.playwright.yml run --rm playwright \
#     npx playwright test tests/e2e/visual-regression.spec.ts --update-snapshots

FROM mcr.microsoft.com/playwright:v1.58.2-noble

WORKDIR /app

# Install dependencies (node_modules are not mounted — built fresh in container)
COPY package.json package-lock.json ./
RUN npm ci

# Copy config files needed by Playwright and Next.js dev server
COPY playwright.config.ts tsconfig.json next.config.ts postcss.config.mjs ./

# Create output directories and make /app writable so any UID (via
# docker-compose user: override) can create .next/ build cache,
# test-results/, and playwright-report/.
RUN mkdir -p test-results playwright-report .next node_modules/.cache \
    && chmod 777 /app test-results playwright-report .next node_modules/.cache

# Tests and source are bind-mounted at runtime via docker-compose
# so baselines written by --update-snapshots persist on the host.
