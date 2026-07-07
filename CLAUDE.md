# CLAUDE.md — Webapp (Dockerized Frontend)

You're building and maintaining a web application that runs in **Docker containers**. Reasoning is your job; execution is the container's job. Containers give you a reproducible, deterministic environment so the app behaves the same everywhere — never fight that by running things on the host.

**Core principle:** Probabilistic AI (you) handles design decisions and orchestration. Deterministic infrastructure (Docker, build scripts, CI) handles execution. Keep those separate and the system stays reliable.

---

## Always Do First
- **Invoke the `frontend-design` skill** before writing any frontend code, every session, no exceptions.
- **Confirm the stack is up** before doing anything visual: `docker compose ps`. If it's not running, start it (see below).

---

## Docker — The Golden Rules
- **The app runs in containers, never directly on the host.** Do not `npm run dev`, `python app.py`, or install dependencies on the host machine.
- **Orchestrate with `docker compose`.** All services (frontend, backend, db, etc.) are defined in `docker-compose.yml`.
- **Never install deps on the host.** If a dependency changes, add it to the manifest (`package.json`, etc.) and **rebuild the image** — don't patch the running container by hand.

### Common commands
- Start (detached): `docker compose up -d`
- Rebuild after dependency or Dockerfile changes: `docker compose up -d --build`
- Follow logs: `docker compose logs -f <service>`
- Run a command inside a service: `docker compose exec <service> <cmd>`
- Stop: `docker compose down` (add `-v` only when you intend to wipe volumes — **ask first**)

### Image & build hygiene
- Pin base image versions (`node:20-alpine`, not `node:latest`).
- Use multi-stage builds: build in one stage, ship a lean runtime stage.
- Maintain a `.dockerignore` (exclude `node_modules`, `.git`, `.env`, `temporary screenshots/`, build output).
- Use bind-mount volumes for hot-reload in dev; don't bake source into the dev image.

### Secrets & config
- All config via environment variables. Secrets live in **`.env`**, passed through `docker-compose.yml` — **never hardcoded, never committed.**
- If a service needs a new variable, add it to `.env.example` (without the real value) so the setup stays reproducible.

---

## Project Commands
This is a React + Vite + Tailwind SPA (`baller-connections`). All commands run inside the `frontend` container, never on the host.
- Start dev server (hot reload on `http://localhost:3000`): `docker compose up -d --build`
- Lint: `docker compose exec frontend npm run lint`
- Production build (writes to `dist/` inside the image, `build` stage): `docker compose build --target build`
- After editing `package.json`, `Dockerfile`, or `docker-compose.yml`: `docker compose up -d --build` to pick up the change — a plain `up -d` reuses the stale image.

---

## Architecture
- **Dockerfile** is multi-stage: `dev` (Vite dev server, source bind-mounted for hot reload — this is the target `docker-compose.yml` runs), `build` (`npm run build` → static `dist/`), and `runtime` (serves `dist/` via `serve` — only relevant if/when this ships to production; the compose stack never builds this stage).
- **docker-compose.yml** defines a single `frontend` service on the `dev` target, bind-mounting the repo into `/app` with an anonymous volume over `/app/node_modules` so host and container dependency trees don't collide.
- **Tailwind** config (`tailwind.config.js`) defines the `pitch` color scale (this project's brand palette per the Anti-Generic Guardrails below — do not fall back to default Tailwind blue/indigo) and the `display`/`sans` font pairing.
- **ESLint** uses flat config (`eslint.config.js`, ESLint 9) — `eslint-plugin-react-hooks` is pinned to `^5.x` since `4.x` doesn't support ESLint 9's peer range.
- No backend/API yet — `src/App.jsx` is a placeholder; the actual connections-game UI, board/puzzle logic, and any data layer are still to be built.

---

## Reference Images
- If a reference image is provided: match layout, spacing, typography, and color **exactly**. Swap in placeholder content (images via `https://placehold.co/`, generic copy). Do not improve or add to the design.
- If no reference image: design from scratch with high craft (see guardrails below).
- Screenshot your output, compare against reference, fix mismatches, re-screenshot. Do **at least 2** comparison rounds. Stop only when no visible differences remain or the user says so.

---

## Serving & Screenshot Workflow (Dockerized)
- **The app is served by a container**, mapped to a host port (e.g. `http://localhost:3000`). Never screenshot a `file:///` URL.
- Bring the stack up first (`docker compose up -d`), confirm the port responds, **then** screenshot.
- **Always screenshot against the mapped localhost port**, e.g. `node screenshot.mjs http://localhost:3000`.
  - If your screenshot tooling (Puppeteer) runs on the host, point it at the mapped port.
  - If it runs in its own container, make sure it shares a network with the app service and targets the service name/port.
- Screenshots save to `./temporary screenshots/screenshot-N.png` (auto-incremented, never overwritten). Optional label: `node screenshot.mjs http://localhost:3000 label` → `screenshot-N-label.png`.
- After screenshotting, **read the PNG with the Read tool** and analyze it directly.
- When comparing, be specific: "heading is 32px but reference shows ~24px", "card gap is 16px but should be 24px".
- Check: spacing/padding, font size/weight/line-height, colors (exact hex), alignment, border-radius, shadows, image sizing.

---

## Output Defaults
- Follow the **project's existing structure** (framework/components/build step). Only fall back to a single `index.html` with inline styles when there's no established structure.
- Tailwind: use the project's configured Tailwind. Only use the CDN (`<script src="https://cdn.tailwindcss.com"></script>`) for throwaway prototypes.
- Placeholder images: `https://placehold.co/WIDTHxHEIGHT`
- Mobile-first responsive.

---

## Brand Assets
- Always check the `brand_assets/` folder before designing. It may contain logos, color guides, style guides, or images.
- If assets exist there, use them. Do not use placeholders where real assets are available.
- If a logo is present, use it. If a color palette is defined, use those **exact values** — do not invent brand colors.

---

## Anti-Generic Guardrails
- **Colors:** Never use the default Tailwind palette (indigo-500, blue-600, etc.). Pick a custom brand color and derive from it.
- **Shadows:** Never use flat `shadow-md`. Use layered, color-tinted shadows with low opacity.
- **Typography:** Never use the same font for headings and body. Pair a display/serif with a clean sans. Apply tight tracking (`-0.03em`) on large headings, generous line-height (`1.7`) on body.
- **Gradients:** Layer multiple radial gradients. Add grain/texture via SVG noise filter for depth.
- **Animations:** Only animate `transform` and `opacity`. Never `transition-all`. Use spring-style easing.
- **Interactive states:** Every clickable element needs hover, focus-visible, and active states. No exceptions.
- **Images:** Add a gradient overlay (`bg-gradient-to-t from-black/60`) and a color treatment layer with `mix-blend-multiply`.
- **Spacing:** Use intentional, consistent spacing tokens — not random Tailwind steps.
- **Depth:** Surfaces should have a layering system (base → elevated → floating), not all sit at the same z-plane.

---

## GitHub Practices
- **Never commit to `main` directly.** Work on a feature branch and open a PR.
- **Branch naming:** short and descriptive, prefixed by type — `feat/pricing-page`, `fix/nav-overflow`, `chore/bump-deps`.
- **Commits:** small, atomic, one logical change each. Imperative mood, Conventional Commits style — `feat: add hero section`, `fix: correct card gap`, `chore: update Dockerfile base image`.
- **Review before you commit:** run `git status` and `git diff` so you know exactly what's staged. No blind `git add .`.
- **Never commit secrets or noise.** Keep a real `.gitignore` covering: `.env`, `node_modules/`, build output (`dist/`, `build/`), `temporary screenshots/`, `credentials.json`, `token.json`, and local Docker overrides you don't want shared.
- **Stay current:** pull/rebase onto the base branch before starting and before opening a PR. Resolve conflicts deliberately, don't blindly accept.
- **Pull requests:** keep them focused and small, write a clear description of what and why, and make sure CI passes before merge.
- **Ask before anything destructive or shared-history-altering:** `push --force`, `reset --hard`, `rebase` on a shared branch, deleting branches, or rewriting published history. When in doubt, `--force-with-lease` over `--force`, and check with me first.

---

## Self-Improvement Loop
When something breaks (a build fails, a container won't come up, a workflow step is flaky):
1. Read the full error and trace.
2. Fix the root cause (Dockerfile, compose config, script), not the symptom.
3. Verify the fix by rebuilding/re-running.
4. Note anything worth remembering (a required env var, a build-order quirk) so it doesn't bite again.
5. Move on with a more robust setup.

If a step uses paid API calls or credits, check with me before re-running.

---

## Hard Rules
- Do not run the app on the host — it runs in Docker.
- Do not install dependencies on the host; add them to the manifest and rebuild.
- Do not commit secrets, `.env`, `node_modules`, build artifacts, or screenshots.
- Do not commit to `main` directly or force-push shared branches without asking.
- Do not add sections, features, or content not in the reference.
- Do not "improve" a reference design — match it.
- Do not stop after one screenshot pass — do at least two.
- Do not use `transition-all`.
- Do not use default Tailwind blue/indigo as the primary color.