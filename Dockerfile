# --- dev: hot-reload dev server, source is bind-mounted in via compose ---
FROM node:20-alpine AS dev
WORKDIR /app
# puppeteer is host-only screenshot tooling; never pull Chromium into the image
ENV PUPPETEER_SKIP_DOWNLOAD=true
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# --- build: produce static production assets ---
FROM node:20-alpine AS build
WORKDIR /app
ENV PUPPETEER_SKIP_DOWNLOAD=true
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# --- runtime: lean static file server ---
FROM node:20-alpine AS runtime
WORKDIR /app
RUN npm install -g serve@14
COPY --from=build /app/dist ./dist
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
