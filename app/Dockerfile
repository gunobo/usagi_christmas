# 1) Expo 웹 빌드
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npx expo export -p web

# 2) nginx로 서빙 + /api, /player는 FastAPI로 프록시
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
