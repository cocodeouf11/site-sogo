# syntax=docker/dockerfile:1.6
# Build stage
FROM node:20-alpine AS build
WORKDIR /app

# Copy manifest (yarn.lock is optional — if missing yarn will resolve fresh)
COPY frontend/package.json ./
# Copy yarn.lock if it exists (glob pattern - won't fail if missing)
COPY frontend/yarn.loc[k] ./
RUN yarn install --network-timeout 100000

# Copy the rest of the frontend
COPY frontend/ ./

# The runtime backend URL can be baked at build time.
# Override via `docker build --build-arg REACT_APP_BACKEND_URL=https://sogo.cocodeouf-server-game.fr`.
ARG REACT_APP_BACKEND_URL=""
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

RUN yarn build

# Serve stage
FROM nginx:1.27-alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
