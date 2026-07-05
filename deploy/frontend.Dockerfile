# syntax=docker/dockerfile:1.6
# Build stage
FROM node:20-alpine AS build
WORKDIR /app

# Speed: only copy manifests first
COPY frontend/package.json frontend/yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 100000

# Copy the rest of the frontend
COPY frontend/ ./

# The runtime backend URL can be baked at build time.
# Override via `docker build --build-arg REACT_APP_BACKEND_URL=https://picking.example.com`.
ARG REACT_APP_BACKEND_URL=http://localhost:8001
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

RUN yarn build

# Serve stage
FROM nginx:1.27-alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
