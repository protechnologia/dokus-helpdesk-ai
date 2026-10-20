# Obraz usługi `frontend`, w trzech etapach do wyboru przez `target` w compose:
#
# | etap    | do czego                                                                  |
# |---------|---------------------------------------------------------------------------|
# | `dev`   | serwer Vite; compose montuje na niego `src/` i `index.html` z hosta        |
# | `build` | buduje pliki strony do `dist/`                                            |
# | `prod`  | nginx: pliki z etapu `build` i przekazywanie `/api/…` do usługi `api`      |
#
# Obrazy bazowe przypięte digestem: ruchomy tag dałby przy przebudowie inny obraz niż testowany.

FROM node:24-alpine@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f AS deps

WORKDIR /app

# Najpierw same zależności: warstwa z `npm ci` przebudowuje się tylko po zmianie wersji.
COPY package.json package-lock.json ./
RUN npm ci

# --- dev: serwer Vite na porcie 8000; źródła montuje compose, więc zmiany są widoczne od razu ---
FROM deps AS dev

COPY . .

CMD ["npm", "run", "dev"]

# --- build: sprawdzenie typów i pliki strony w dist/ ---
FROM deps AS build

COPY . .

RUN npm run build

# --- prod: nginx z plikami strony; szablon konfiguracji obraz wypełnia przy starcie ---
FROM nginx:1.30-alpine@sha256:970364228b1e4f932abc22d321932816782cca8a20b85a77552a7cfe9acfb3b5 AS prod

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
